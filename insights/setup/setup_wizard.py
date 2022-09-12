# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _


def get_setup_stages(args=None):
    # to make setup wizard tasks run in a background job
    frappe.local.conf["trigger_site_setup_in_background"] = 1

    if frappe.db.sql("select name from `tabData Source`"):
        stages = [
            {
                "status": _("Wrapping up"),
                "fail_msg": _("Failed to login"),
                "tasks": [
                    {"fn": wrap_up, "args": args, "fail_msg": _("Failed to login")}
                ],
            }
        ]
    else:
        if args.get("setup_demo_db"):
            database_setup_stages = get_demo_setup_stages()
        else:
            database_setup_stages = [
                {
                    "status": _("Creating Data Source"),
                    "fail_msg": _("Failed to create Data Source"),
                    "tasks": [
                        {
                            "fn": create_datasource,
                            "args": args,
                            "fail_msg": _("Failed to create Data Source"),
                        }
                    ],
                }
            ]

        stages = database_setup_stages + [
            {
                "status": _("Wrapping up"),
                "fail_msg": _("Failed to login"),
                "tasks": [
                    {"fn": wrap_up, "args": args, "fail_msg": _("Failed to login")}
                ],
            },
        ]

    return stages


def get_demo_setup_stages():
    from insights.setup.demo import (
        initialize_demo_setup,
        download_demo_data,
        extract_demo_data,
        create_entries,
        create_indexes,
        create_data_source,
        create_table_links,
        cleanup,
    )

    stages_by_fn = {
        _("Starting demo setup"): initialize_demo_setup,
        _("Downloading data"): download_demo_data,
        _("Extracting data"): extract_demo_data,
        _("Inserting data"): create_entries,
        _("Optimizing reads"): create_indexes,
        _("Creating datasource"): create_data_source,
        _("Creating links"): create_table_links,
        _("Finishing demo setup"): cleanup,
    }

    stages = []
    for stage_name, fn in stages_by_fn.items():
        stages.append(
            {
                "status": stage_name,
                "fail_msg": _("Failed to setup demo data"),
                "tasks": [
                    {
                        "fn": run_stage_task,
                        "args": frappe._dict({"task": fn}),
                        "fail_msg": _("Failed to setup demo data"),
                    }
                ],
            }
        )

    return stages


# this weird function exists
# because all stage task must have one argument (args)
def run_stage_task(args):
    return args.task()


def create_datasource(args):
    data_source = frappe.new_doc("Data Source")
    data_source.update(
        {
            "database_type": args.get("db_type"),
            "database_name": args.get("db_name"),
            "title": args.get("db_title"),
            "host": args.get("db_host"),
            "port": args.get("db_port"),
            "username": args.get("db_username"),
            "password": args.get("db_password"),
            "use_ssl": args.get("db_use_ssl"),
        }
    )
    data_source.save()


def wrap_up(args):
    frappe.local.message_log = []
    login_as_first_user(args)

    settings = frappe.get_single("Insights Settings")
    settings.setup_complete = 1
    settings.save()


def login_as_first_user(args):
    if args.get("email") and hasattr(frappe.local, "login_manager"):
        frappe.local.login_manager.login_as(args.get("email"))


@frappe.whitelist()
def test_db_connection(db):
    from frappe.database.mariadb.database import MariaDBDatabase
    from frappe.utils import cint

    if type(db) is not dict:
        db = frappe.parse_json(db)

    db = frappe._dict(db)

    if db.db_type == "MariaDB":
        try:
            db_instance = MariaDBDatabase(
                host=db.db_host,
                port=cint(db.db_port),
                user=db.db_username,
                password=db.db_password,
            )
            db_instance.sql("select 1")
            return True
        except BaseException:
            frappe.log_error(title="Setup Wizard Database Connection Error")
            return False