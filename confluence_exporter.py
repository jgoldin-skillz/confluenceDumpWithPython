import os.path
import argparse
import myModules


class ConfluenceExporter:
    def __init__(
        self,
        mode,
        site,
        space=None,
        page=None,
        label=None,
        outdir="output",
        sphinx=False,
        tags=False,
        html=False,
        rst=True,
        showlabels=False,
    ):
        self.mode = mode
        self.site = site
        self.space = space
        self.page = page
        self.label = label
        self.outdir = outdir
        self.sphinx = sphinx
        self.tags = tags
        self.html = html
        self.rst = rst
        self.showlabels = showlabels

        self.user_name = os.environ["atlassianUserEmail"]
        self.api_token = os.environ["atlassianAPIToken"]

    def export(self):
        if self.mode == "single":
            self._export_single_page()
        elif self.mode == "space":
            self._export_space()
        elif self.mode == "bylabel":
            self._export_by_label()
        elif self.mode == "pageprops":
            self._export_page_properties()
        else:
            print(
                "Invalid mode. Choose from 'single', 'space', 'bylabel', or 'pageprops'."
            )

    def _export_single_page(self):
        print(f"Exporting a single page (Sphinx set to {self.sphinx})")
        page_id = self.page
        page_name = myModules.get_page_name(
            self.site, page_id, self.user_name, self.api_token
        )

        my_body_export_view = myModules.get_body_export_view(
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

        page_url = f"{my_body_export_view['_links']['base']}{my_body_export_view['_links']['webui']}"
        page_parent = myModules.get_page_parent(
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
        my_outdirs = myModules.mk_outdirs(
            my_outdir_base
        )  # attachments, embeds, scripts
        my_page_labels = myModules.get_page_labels(
            self.site, page_id, self.user_name, self.api_token
        )
        print(
            f'Base export folder is "{my_outdir_base}" and the Content goes to "{my_outdir_content}"'
        )
        myModules.dump_html(
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
        print("Done!")

    def _export_space(self):
        print(f"Exporting a whole space (Sphinx set to {self.sphinx})")
        space_key = self.space
        all_spaces_full = myModules.get_spaces_all(
            self.site, self.user_name, self.api_token
        )  # get a dump of all spaces
        all_spaces_short = []  # initialize list for less detailed list of spaces
        i = 0
        for n in all_spaces_full:
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
                print("Found space: " + n["key"])
                space_id = n["id"]
                space_name = n["name"]
                current_parent = n["homepageId"]
        my_outdir_content = os.path.join(self.outdir, f"{space_id}-{space_name}")
        if not os.path.exists(my_outdir_content):
            os.mkdir(my_outdir_content)
        if self.sphinx is False:
            my_outdir_base = my_outdir_content

        # print("my_outdir_base: " + my_outdir_base)
        # print("my_outdir_content: " + my_outdir_content)

        if (
            space_key == "" or space_key is None
        ):  # if the supplied space key can't be found
            print("Could not find Space Key in this site")
        else:
            space_title = myModules.get_space_title(
                self.site, space_id, self.user_name, self.api_token
            )
            #
            # get list of pages from space
            #
            all_pages_full = myModules.get_pages_from_space(
                self.site, space_id, self.user_name, self.api_token
            )
            all_pages_short = []
            i = 0
            for n in all_pages_full:
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
            print(f"{len(all_pages_short)} pages to export")
            page_counter = 0
            for p in all_pages_short:
                page_counter = page_counter + 1
                my_body_export_view = myModules.get_body_export_view(
                    self.site, p["page_id"], self.user_name, self.api_token
                ).json()
                my_body_export_view_html = my_body_export_view["body"]["export_view"][
                    "value"
                ]
                my_body_export_view_name = p["pageTitle"]
                my_body_export_view_title = (
                    p["pageTitle"]
                    .replace("/", "-")
                    .replace(",", "")
                    .replace("&", "And")
                    .replace(" ", "_")
                )  # added .replace(" ","_") so that filenames have _ as a separator
                print()
                print(
                    f"Getting page #{page_counter}/{len(all_pages_short)}, {my_body_export_view_title}, {p['page_id']}"
                )
                my_body_export_view_labels = myModules.get_page_labels(
                    self.site, p["page_id"], self.user_name, self.api_token
                )
                # my_body_export_view_labels = ",".join(myModules.get_page_labels(atlassian_site,p['page_id'],user_name,api_token))
                mypage_url = f"{my_body_export_view['_links']['base']}{my_body_export_view['_links']['webui']}"
                print(f"dump_html arg sphinx_compatible = {self.sphinx}")
                myModules.dump_html(
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
        print("Done!")

    def _export_by_label(self):
        pass  # Replace with actual implementation

    def _export_page_properties(self):
        my_page_properties_children = []
        my_page_properties_children_dict = {}

        page_id = self.page
        #
        # Get Page Properties REPORT
        #
        print("Getting Page Properties Report Details")
        my_report_export_view = myModules.get_body_export_view(
            self.site, page_id, self.user_name, self.api_token
        ).json()
        my_report_export_view_title = (
            my_report_export_view["title"]
            .replace("/", "-")
            .replace(",", "")
            .replace("&", "And")
            .replace(":", "-")
        )
        my_report_export_view_html = my_report_export_view["body"]["export_view"][
            "value"
        ]
        my_report_export_viewName = myModules.get_page_name(
            self.site, page_id, self.user_name, self.api_token
        )
        my_report_export_view_labels = myModules.get_page_labels(
            self.site, page_id, self.user_name, self.api_token
        )
        my_report_export_page_url = f"{my_report_export_view['_links']['base']}{my_report_export_view['_links']['webui']}"
        my_report_export_page_parent = myModules.get_page_parent(
            self.site, page_id, self.user_name, self.api_token
        )
        my_report_export_html_filename = f"{my_report_export_view_title}.html"
        # str(my_report_export_view_title) + '.html'
        # my outdirs
        my_outdir_content = os.path.join(
            self.outdir, str(page_id) + "-" + str(my_report_export_view_title)
        )
        # print("my_outdir_base: " + my_outdir_base)
        # print("my_outdir_content: " + my_outdir_content)
        if self.sphinx is False:
            my_outdir_base = my_outdir_content

        my_outdirs = []
        my_outdirs = myModules.mk_outdirs(
            my_outdir_base
        )  # attachments, embeds, scripts
        # get info abbout children
        # my_page_properties_children = myModules.get_page_properties_children(atlassian_site,my_report_export_view_html,my_outdir_content,user_name,api_token)[0]          # list
        # my_page_properties_children_dict = myModules.get_page_properties_children(atlassian_site,my_report_export_view_html,my_outdir_content,user_name,api_token)[1]      # dict
        (my_page_properties_children, my_page_properties_children_dict) = (
            myModules.get_page_properties_children(
                self.site,
                my_report_export_view_html,
                my_outdir_content,
                self.user_name,
                self.api_token,
            )
        )
        #
        # Get Page Properties CHILDREN
        #
        page_counter = 0
        for p in my_page_properties_children:
            page_counter = page_counter + 1
            # print("Handling child: " + p)
            my_child_export_view = myModules.get_body_export_view(
                self.site, p, self.user_name, self.api_token
            ).json()
            my_child_export_view_html = my_child_export_view["body"]["export_view"][
                "value"
            ]
            my_child_export_view_name = my_page_properties_children_dict[p]["Name"]
            my_child_export_view_labels = myModules.get_page_labels(
                self.site, p, self.user_name, self.api_token
            )
            my_child_export_view_title = my_child_export_view[
                "title"
            ]  ##.replace("/","-").replace(":","-").replace(" ","_")
            print(
                f"Getting Child page #{page_counter}/{len(my_page_properties_children)}, {my_child_export_view_title}, {my_page_properties_children_dict[str(p)]['ID']}"
            )
            # print("Getting Child page #" + str(page_counter) + '/' + str(len(my_page_properties_children)) + ', ' + my_child_export_view_title + ', ' + my_page_properties_children_dict[str(p)]['ID'])
            my_child_export_page_url = f"{my_child_export_view['_links']['base']}{my_child_export_view['_links']['webui']}"
            # my_child_export_page_url = str(my_child_export_view['_links']['base']) + str(my_child_export_view['_links']['webui'])
            my_child_export_page_parent = myModules.get_page_parent(
                self.site, p, self.user_name, self.api_token
            )
            html_file_name = (
                (f"{my_page_properties_children_dict[p]['Name']}.html")
                .replace(":", "-")
                .replace(" ", "_")
            )
            # html_file_name = my_page_properties_children_dict[p]['Name'].replace(":","-").replace(" ","_") + '.html'
            my_page_properties_children_dict[str(p)].update(
                {"Filename": html_file_name}
            )

            myModules.dump_html(
                arg_site=self.site,
                arg_html=my_child_export_view_html,
                arg_title=my_child_export_view_title,
                arg_page_id=p,
                arg_outdir_base=my_outdir_base,
                arg_outdir_content=my_outdir_content,
                arg_page_labels=my_child_export_view_labels,
                arg_page_parent=my_child_export_page_parent,
                arg_username=self.user_name,
                arg_api_token=self.api_token,
                arg_sphinx_compatible=self.sphinx,
                arg_sphinx_tags=self.tags,
                arg_type="reportchild",
                arg_html_output=self.html,
                arg_rst_output=self.rst,
                arg_show_labels=self.showlabels,
            )  # creates html files for every child
        myModules.dump_html(
            arg_site=self.site,
            arg_html=my_report_export_view_html,
            arg_title=my_report_export_view_title,
            arg_page_id=page_id,
            arg_outdir_base=my_outdir_base,
            arg_outdir_content=my_outdir_content,
            arg_page_labels=my_report_export_view_labels,
            arg_page_parent=my_report_export_page_parent,
            arg_username=self.user_name,
            arg_api_token=self.api_token,
            arg_sphinx_compatible=self.sphinx,
            arg_sphinx_tags=self.tags,
            arg_type="report",
            arg_html_output=self.html,
            arg_rst_output=self.rst,
            arg_show_labels=self.showlabels,
        )  # finally creating the HTML for the report page
        print("Done!")


if __name__ == "__main__":
    # Argument parsing remains similar (using argparse)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        "-m",
        dest="mode",
        choices=["single", "space", "bylabel", "pageprops"],
        help="Chose a download mode",
        required=True,
    )
    parser.add_argument("--site", "-S", type=str, help="Atlassian Site", required=True)
    parser.add_argument("--space", "-s", type=str, help="Space Key")
    parser.add_argument("--page", "-p", type=int, help="Page ID")
    parser.add_argument("--label", "-l", type=str, help="Page label")
    parser.add_argument(
        "--outdir",
        "-o",
        type=str,
        default="output",
        help="Folder for export",
        required=False,
    )
    parser.add_argument(
        "--sphinx",
        "-x",
        action="store_true",
        default=False,
        help="Sphinx compatible folder structure",
        required=False,
    )
    parser.add_argument(
        "--tags",
        action="store_true",
        default=False,
        help="Add labels as .. tags::",
        required=False,
    )
    parser.add_argument(
        "--html",
        action="store_true",
        default=False,
        help="Include .html file in export (default is only .rst)",
        required=False,
    )
    parser.add_argument(
        "--no-rst",
        action="store_false",
        dest="rst",
        default=True,
        help="Disable .rst file in export",
        required=False,
    )
    parser.add_argument(
        "--showlabels",
        action="store_true",
        default=False,
        help="Export .rst files with the page labels at the bottom",
        required=False,
    )

    args = parser.parse_args()

    exporter = ConfluenceExporter(
        args.mode,
        args.site,
        args.space,
        args.page,
        args.label,
        args.outdir,
        args.sphinx,
        args.tags,
        args.html,
        args.rst,
        args.showlabels,
    )
    exporter.export()
