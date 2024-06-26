import os.path
import json
import signal
import time
import logging
from dateutil import parser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from humanfriendly import format_timespan
from datetime import timezone
from confluence_dump.myModules import get_page_last_modified, get_page_name, get_body_export_view, get_page_parent, mk_outdirs, get_page_labels, dump_html, get_spaces_all, get_space_title, get_pages_from_space, get_page_properties_children


class ConfluenceExporter:
    def __init__(
        self,
        site,
        space,
        outdir="output",
        sphinx=False,
        tags=False,
        html=False,
        rst=True,
        showlabels=False,
        api_username=None,
        api_token=None,
        log_interval=5,  # Log progress every 5 seconds
        start_date: datetime = None,
        end_date: datetime = None,
        workers: int = 4
    ):
        self.site = site
        self.space = space
        self.outdir = outdir
        self.sphinx = sphinx
        self.tags = tags
        self.html = html
        self.rst = rst
        self.showlabels = showlabels
        self.log_interval = log_interval
        self.interrupted = False
        self.start_date = start_date
        self.end_date = end_date
        self.workers = workers
        signal.signal(signal.SIGINT, self.signal_handler)
        
        global interrupted
        interrupted = False

        # Get API credentials from arguments or environment variables
        self.user_name = api_username or os.environ.get("atlassianUserEmail")
        self.api_token = api_token or os.environ.get("atlassianAPIToken")

        # Set up logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    def signal_handler(self, signal, frame):
        print('Ctrl+C caught! Exiting gracefully...')
        global interrupted
        interrupted = True
        self.interrupted = True
        exit(1)

    def export_single_page(self, page_id, **kwargs):
        start_time = time.time()
        # Update attributes with kwargs if provided
        for key, value in kwargs.items():
            setattr(self, key, value)

        logging.info(f"Exporting a single page (Sphinx set to {self.sphinx})")
        page_id = page_id
        
        last_modified = get_page_last_modified(
            self.site, page_id, self.user_name, self.api_token
        )
        last_modified_date = datetime.fromisoformat(last_modified)
        
        if self.start_date and last_modified_date < self.start_date:
            logging.info(f"Page {page_id} was last modified on {last_modified_date}, which is before the start date {self.start_date}. Skipping.")
            return
        
        if self.end_date and last_modified_date > self.end_date:
            logging.info(f"Page {page_id} was last modified on {last_modified_date}, which is after the end date {self.end_date}. Skipping.")
            return
        
        page_name = get_page_name(
            self.site, page_id, self.user_name, self.api_token
        )

        my_body_export_view = get_body_export_view(
            self.site, page_id, self.user_name, self.api_token
        ).json()
        my_body_export_view_html = my_body_export_view["body"]["export_view"]["value"]
        my_body_export_view_title = (
            my_body_export_view["title"]
            .replace("/", "-")
            .replace(",", "")
            .replace("&", "And")
            .replace(":", "-")
        )

        server_url = f"https://{self.site}.atlassian.net/wiki/api/v2/spaces/?limit=250"

        page_url = f"{my_body_export_view['_links']['base']}"
        page_parent = get_page_parent(
            self.site, page_id, self.user_name, self.api_token
        )

        my_outdir_base = os.path.join(
            self.outdir, f"{page_id}-{my_body_export_view_title}"
        )  # sets outdir to path under page_name
        my_outdir_content = my_outdir_base

        #    if args.sphinx is False:
        #        my_outdir_base = os.path.join(my_outdir_base,f"{page_id}-{my_body_export_view_title}")        # sets outdir to path under page_name
        #        my_outdir_content = my_outdir_base
        #    else:
        #        my_outdir_content = my_outdir_base
        my_outdirs = []
        my_outdirs = mk_outdirs(
            my_outdir_base
        )  # attachments, embeds, scripts
        my_page_labels = get_page_labels(
            self.site, page_id, self.user_name, self.api_token
        )
        logging.info(
            f'Base export folder is "{my_outdir_base}" and the Content goes to "{my_outdir_content}"'
        )
        try:
            url, dumped_file_path = dump_html(
                self.site,
                my_body_export_view_html,
                my_body_export_view_title,
                page_id,
                my_outdir_base,
                my_outdir_content,
                my_page_labels,
                page_parent,
                self.user_name,
                self.api_token,
                self.sphinx,
                self.tags,
                arg_html_output=self.html,
                arg_rst_output=self.rst,
            )
        except Exception as e:
            logging.error(f"Error exporting page {page_id}: {e}")
            return None, None, None, None, None, None
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Done! Exporting single page took {format_timespan(elapsed_time)}.")
        return my_body_export_view_title, page_id, url, dumped_file_path, self.space, self.site

    def export_space(self, **kwargs):
        global last_log_time
        start_time = time.time()
        last_log_time = start_time
        global filtered_pages_count
        filtered_pages_count = 0
        global page_counter
        page_counter = 0
        global interrupted
        # Update attributes with kwargs if provided
        for key, value in kwargs.items():
            setattr(self, key, value)

        logging.info(f"Exporting a whole space (Sphinx set to {self.sphinx})")
        space_key = self.space
        all_spaces_full = get_spaces_all(
            self.site, self.user_name, self.api_token
        )  # get a dump of all spaces
        all_spaces_short = []  # initialize list for less detailed list of spaces
        i = 0
        for n in all_spaces_full:
            global interrupted
            if interrupted or self.interrupted:
                logging.warning("Interrupting export of space")
                return
            i = i + 1
            all_spaces_short.append(
                {  # append the list of spaces
                    "space_key": n["key"],
                    "space_id": n["id"],
                    "space_name": n["name"],
                    "homepage_id": n["homepageId"],
                    "spaceDescription": n["description"],
                }
            )
            if (
                (n["key"] == space_key)
                or n["key"] == str.upper(space_key)
                or n["key"] == str.lower(space_key)
            ):
                logging.info("Found space: " + n["key"])
                space_id = n["id"]
                space_name = n["name"]
                current_parent = n["homepageId"]
        my_outdir_content = os.path.join(
            self.outdir, f"{space_id}-{space_name}")
        os.makedirs(my_outdir_content, exist_ok=True)
        if self.sphinx is False:
            my_outdir_base = my_outdir_content

        # print("my_outdir_base: " + my_outdir_base)
        # print("my_outdir_content: " + my_outdir_content)

        if (
            space_key == "" or space_key is None
        ):  # if the supplied space key can't be found
            logging.error("Could not find Space Key in this site")
        else:
            space_title = get_space_title(
                self.site, space_id, self.user_name, self.api_token
            )
            #
            # get list of pages from space
            #
            all_pages_full = get_pages_from_space(
                self.site, space_id, self.user_name, self.api_token
            )
            all_pages_short = []
            i = 0
            for n in all_pages_full:
                if self.interrupted:
                    logging.warning("Interrupting export of space")
                    return
                i = i + 1
                all_pages_short.append(
                    {
                        "page_id": n["id"],
                        "pageTitle": n["title"],
                        "parentId": n["parentId"],
                        "space_id": n["spaceId"],
                    }
                )
            # put it all together
            logging.info(f"{len(all_pages_short)} pages to export")
            
            page_counter = 0
            total_pages = len(all_pages_short)
            dumped_file_paths = {}
            # Filter pages based on date criteria if start_date or end_date are provided
            start_time = time.time()
            last_log_time = start_time
            page_counter = 0
            filtered_pages_count = 0

            def filter_page(p):
                global last_log_time
                global filtered_pages_count
                global page_counter
                global interrupted
                if interrupted or self.interrupted:
                    return None
                now = time.time()
                if now - last_log_time >= self.log_interval:
                    estimated_time_remaining = (now - start_time) / (page_counter + 1) * (total_pages - page_counter - 1)
                    logging.info(f"Processing page {page_counter}/{total_pages} for {filtered_pages_count} filtered pages so far. Time elapsed: {format_timespan(now - start_time)}, estimated time remaining: {format_timespan(estimated_time_remaining)}.")
                    last_log_time = now

                last_modified_str = get_page_last_modified(
                    self.site, p["page_id"], self.user_name, self.api_token
                )
                last_modified = parser.isoparse(last_modified_str).replace(tzinfo=timezone.utc)
                
                page_counter += 1
                if (not self.start_date or last_modified >= self.start_date) and (not self.end_date or last_modified <= self.end_date):
                    filtered_pages_count += 1
                    return p
                return None

            if self.start_date or self.end_date:
                with ThreadPoolExecutor(max_workers=self.workers) as executor:
                    results = list(executor.map(filter_page, all_pages_short))
                filtered_pages = [page for page in results if page is not None]
                total_pages = len(filtered_pages)
                logging.info(f"{total_pages} pages meet the date criteria and will be processed.")
            else:
                filtered_pages = all_pages_short
                logging.info("No date filtering applied.")

            logging.info(f"Starting export of {len(filtered_pages)} pages")
            page_counter = 0
            for p in filtered_pages:
                if self.interrupted:
                    logging.warning("Interrupting export of space")
                    return
                try:
                    page_counter += 1
                    now = time.time()
                    
                    if now - last_log_time >= self.log_interval:
                        estimated_time_remaining = (
                            now - start_time) / page_counter * (total_pages - page_counter)
                        logging.info(f"Exporting page {page_counter}/{total_pages} - Estimated time remaining: {format_timespan(estimated_time_remaining)}")
                        last_log_time = now

                    my_body_export_view = get_body_export_view(
                        self.site, p["page_id"], self.user_name, self.api_token
                    ).json()
                    my_body_export_view_html = my_body_export_view["body"]["export_view"]["value"]
                    my_body_export_view_name = p["pageTitle"]
                    my_body_export_view_title = (
                        p["pageTitle"]
                        .replace("/", "-")
                        .replace(",", "")
                        .replace("&", "And")
                        .replace(" ", "_")
                        # added .replace(" ","_") so that filenames have _ as a separator
                    )
                    logging.debug(f"Getting page #{page_counter}/{len(all_pages_short)}, {my_body_export_view_title}, {p['page_id']}")
                    my_body_export_view_labels = get_page_labels(
                        self.site, p["page_id"], self.user_name, self.api_token
                    )
                    # my_body_export_view_labels = ",".join(myModules.get_page_labels(atlassian_site,p['page_id'],user_name,api_token))
                    my_page_url = f"{my_body_export_view['_links']['base']}"

                    logging.debug(f"dump_html arg sphinx_compatible = {self.sphinx}")
                    url, dumped_file_path = dump_html(
                        self.site,
                        my_body_export_view_html,
                        my_body_export_view_title,
                        p["page_id"],
                        my_outdir_base,
                        my_outdir_content,
                        my_body_export_view_labels,
                        p["parentId"],
                        self.user_name,
                        self.api_token,
                        self.sphinx,
                        self.tags,
                        arg_html_output=self.html,
                        arg_rst_output=self.rst,
                    )
                    dumped_file_paths[my_body_export_view_title] = (p["page_id"], url, dumped_file_path, self.space, self.site)
                except Exception as e:
                    logging.error(f"Error exporting page {p['page_id']}: {e}")
                    continue
        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Done! Exporting space took {format_timespan(elapsed_time)}.")
        return dumped_file_paths
