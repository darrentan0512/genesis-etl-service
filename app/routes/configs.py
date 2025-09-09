import random
import re

from flask import Blueprint, jsonify, request

from app import mongo
from app.models.error_response import ErrorResponse
from app.utils.calculating_shift import shift_types

overall_config_bp = Blueprint("overall_config", __name__, url_prefix="/api/configs")


# GET /api/employees/<id> - Get employee by ID
@overall_config_bp.route("/shift_type", methods=["GET"])
def get_shift_type():
    try:
        department = request.headers.get("department")
        company = request.headers.get("company")
        config_type = "SHIFT_TYPE"

        if not company or not department:
            return jsonify(
                {
                    "success": False,
                    "message": "Missing headers fields: DEPARTMENT, COMPANY",
                }
            ), 400
        existing_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
            {"_id": 0, "CONFIG_TYPE": 0, "DEPARTMENT": 0, "COMPANY": 0},
        )
        return jsonify(
            {
                "success": True,
                "data": existing_config["SHIFT_TYPE"]
                if existing_config
                else shift_types,
            }
        ), 200

    except Exception as e:
        return jsonify(
            {"success": False, "message": "Error fetching shift_type", "error": str(e)}
        ), 500


@overall_config_bp.route("/shift_type", methods=["POST"])
def update_shift_type():
    try:
        data = request.get_json()

        if (
            not data
            or "DEPARTMENT" not in data
            or "COMPANY" not in data
            or "SHIFT_TYPE" not in data
        ):
            return jsonify(
                {
                    "success": False,
                    "message": "Missing required fields: DEPARTMENT, COMPANY, SHIFT_TYPE",
                }
            ), 400

        department = data["DEPARTMENT"]
        company = data["COMPANY"]
        config_type = "SHIFT_TYPE"
        new_shift_types = data["SHIFT_TYPE"]

        # Find existing config
        existing_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type}
        )

        if existing_config:
            # Get existing shift types
            existing_shift_types = existing_config.get("SHIFT_TYPE", [])

            # Create a dictionary for quick lookup by type
            existing_types_dict = {
                shift["type"]: shift for shift in existing_shift_types
            }

            # Process new shift types
            for new_shift in new_shift_types:
                shift_type = new_shift.get("type")
                if shift_type in existing_types_dict:
                    # Replace existing shift type
                    existing_types_dict[shift_type] = new_shift
                else:
                    # Add new shift type
                    existing_types_dict[shift_type] = new_shift

            # Convert back to list
            updated_shift_types = list(existing_types_dict.values())

            # Update the document
            mongo.db.configs.update_one(
                {
                    "DEPARTMENT": department,
                    "COMPANY": company,
                    "CONFIG_TYPE": config_type,
                },
                {"$set": {"SHIFT_TYPE": updated_shift_types}},
            )
        else:
            # Create new document
            new_config = {
                "DEPARTMENT": department,
                "COMPANY": company,
                "CONFIG_TYPE": config_type,
                "SHIFT_TYPE": new_shift_types,
            }
            mongo.db.configs.insert_one(new_config)

        # Fetch updated data to return
        updated_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
            {"_id": 0},  # Exclude _id from response
        )

        return jsonify(
            {
                "success": True,
                "message": "Shift types updated successfully",
                "data": updated_config,
            }
        ), 200

    except Exception as e:
        return jsonify(
            {"success": False, "message": "Error updating shift types", "error": str(e)}
        ), 500


@overall_config_bp.route("/department_list", methods=["GET"])
def get_department_list():
    try:
        # Find all employees and extract unique departments
        employees = mongo.db.employee.find({}, {"DEPARTMENT": 1})

        # Extract unique departments, filter out None/null values
        departments = set()
        for employee in employees:
            if employee.get("DEPARTMENT"):
                departments.add(employee["DEPARTMENT"])

        # Convert to list and add DEFAULT option
        department_list = sorted(list(departments))
        department_list.insert(0, "DEFAULT")

        return jsonify({"success": True, "data": department_list}), 200

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": "Error fetching department list from employee db",
                "error": str(e),
            }
        ), 500


@overall_config_bp.route("/role_groups", methods=["GET"])
def get_role_groups():
    try:
        department = request.headers.get("department")
        company = request.headers.get("company")
        config_type = "ROLE_GROUPS"

        if not company or not department:
            return jsonify(
                {
                    "success": False,
                    "message": "Missing headers fields: DEPARTMENT, COMPANY",
                }
            ), 400

        # Filter by department first
        # TODO: to consider if need to account for company
        #   given that different company data will be stored in different db
        # Find all employees and extract unique roles sorted by company and department
        employees = mongo.db.employee.find(
            {
                # "COMPANY": company,
                "DEPARTMENT": department
            },
            {"ROLE": 1},
        )

        # Extract unique roles, filter out None/null values
        roles = set()
        for employee in employees:
            if employee.get("ROLE"):
                roles.add(employee["ROLE"])

        # Convert to list and add DEFAULT option
        role_list = sorted(list(roles))
        # role_list.insert(0, "DEFAULT")
        role_set = set(role_list)  # For faster lookup

        existing_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
            {"_id": 0, "CONFIG_TYPE": 0, "DEPARTMENT": 0, "COMPANY": 0},
        )
        print(f"Existing Config: {existing_config}")

        groups = []
        if existing_config and existing_config.get("GROUPS"):
            for group in existing_config["GROUPS"]:
                group_list = group.get("role_list", [])

                # Find deprecated roles (roles in role_list but not in current role_list)
                deprecated_roles = [role for role in group_list if role not in role_set]

                processed_group = {
                    "label": group.get("label", ""),
                    "role_list": group_list,
                    "deprecated_roles": deprecated_roles,
                }

                groups.append(processed_group)

        # Default response structure
        response = {"LIST": role_list, "GROUPS": groups}

        return jsonify({"success": True, "data": response}), 200

    except Exception as e:
        return jsonify(
            {"success": False, "message": "Error fetching role groups", "error": str(e)}
        ), 500


@overall_config_bp.route("/role_groups", methods=["POST"])
def update_role_groups():
    try:
        data = request.get_json()

        if (
            not data
            or "DEPARTMENT" not in data
            or "COMPANY" not in data
            or "GROUPS" not in data
        ):
            return jsonify(
                {
                    "success": False,
                    "message": "Missing required fields: DEPARTMENT, COMPANY, GROUPS",
                }
            ), 400

        department = data["DEPARTMENT"]
        company = data["COMPANY"]
        config_type = "ROLE_GROUPS"
        new_groups = data["GROUPS"]

        # Find existing config
        existing_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type}
        )

        if existing_config:
            # Get existing groups
            existing_groups = existing_config.get("GROUPS", [])
            existing_list = existing_config.get("LIST", [])

            # Create a dictionary for quick lookup by label
            existing_groups_dict = {group["label"]: group for group in existing_groups}

            # Process new groups
            for new_group in new_groups:
                group_label = new_group.get("label")
                if group_label in existing_groups_dict:
                    # Replace existing group's role_list
                    existing_groups_dict[group_label]["role_list"] = new_group.get(
                        "role_list", []
                    )
                else:
                    # Add new group
                    existing_groups_dict[group_label] = new_group

            # Convert back to list
            updated_groups = list(existing_groups_dict.values())

            # Update the document
            mongo.db.configs.update_one(
                {
                    "DEPARTMENT": department,
                    "COMPANY": company,
                    "CONFIG_TYPE": config_type,
                },
                {
                    "$set": {
                        "GROUPS": updated_groups,
                    }
                },
            )
        else:
            new_config = {
                "DEPARTMENT": department,
                "COMPANY": company,
                "CONFIG_TYPE": config_type,
                "GROUPS": new_groups,
            }
            mongo.db.configs.insert_one(new_config)

        # Fetch updated data to return
        updated_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
            {"_id": 0, "CONFIG_TYPE": 0, "DEPARTMENT": 0, "COMPANY": 0},
        )

        return jsonify(
            {
                "success": True,
                "message": "Role groups updated successfully",
                "data": updated_config,
            }
        ), 200

    except Exception as e:
        return jsonify(
            {"success": False, "message": "Error updating role groups", "error": str(e)}
        ), 500
