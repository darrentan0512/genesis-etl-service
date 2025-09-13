import random
import re
import uuid
from typing import Any

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


def _validate_payload(data):
    """
    Validates that the required fields are present in the request JSON.
    Returns the extracted data or raises a ValueError if validation fails.
    """
    required_fields = ["DEPARTMENT", "COMPANY", "SHIFT_TYPE"]
    if not data or not all(field in data for field in required_fields):
        raise ValueError("Missing required fields: DEPARTMENT, COMPANY, SHIFT_TYPE")

    # Ensure SHIFT_TYPE is a non-empty list
    if not isinstance(data["SHIFT_TYPE"], list) or not data["SHIFT_TYPE"]:
        raise ValueError("SHIFT_TYPE must be a non-empty list of shift objects.")

    return {
        "department": data["DEPARTMENT"],
        "company": data["COMPANY"],
        "new_shift_types": data["SHIFT_TYPE"],
    }


def _collect_validation_errors(new_shift_types, existing_shift_labels):
    """
    Collects field validation and duplicate label errors for new shift types.
    """
    all_errors = []

    # Also track labels within the current request to prevent self-duplication
    request_labels = set()

    for index, shift in enumerate(new_shift_types):
        # 1. Validate individual shift fields (assuming you have this function)
        # If validate_shift_type_fields returns a list of errors for a single shift
        field_errors = validate_shift_type_fields(index, shift)
        if field_errors:
            all_errors.extend(field_errors)
        print(f"field: {field_errors}")

        # 2. Check for duplicates against existing shifts in the database
        label = shift.get("label")
        if label in existing_shift_labels:
            all_errors.append(
                {
                    "shift_label": label,
                    "message": "Duplicate shift label. This shift already exists.",
                    "index": index,
                }
            )

        # 3. Check for duplicates within the same request payload
        if label in request_labels:
            all_errors.append(
                {
                    "shift_label": label,
                    "message": "Duplicate shift label found within the request payload.",
                    "index": index,
                }
            )

        if label:
            request_labels.add(label)

    print(f"all errors: {all_errors}")
    return all_errors


def validate_shift_type_fields(index, shift):
    """
    Placeholder for your detailed field validation logic.
    Checks a single shift object for required keys, data types, etc.
    Returns a list of errors, or an empty list if valid.
    """
    errors = []
    if "label" not in shift or not shift["label"]:
        errors.append({"message": "Field 'label' is missing or empty.", "index": index})
    if "start_time" not in shift:
        errors.append({"message": "Field 'start_time' is missing.", "index": index})
    if "end_time" not in shift:
        errors.append({"message": "Field 'end_time' is missing.", "index": index})
    if "days_applied_to" not in shift:
        errors.append(
            {"message": "Field 'days_applied_to' is missing.", "index": index}
        )
    if "roles_applied_to" not in shift:
        errors.append(
            {"message": "Field 'roles_applied_to' is missing.", "index": index}
        )

    return errors


@overall_config_bp.route("/shift_type/add", methods=["POST"])
def add_shift_type():
    """
    Adds one or more new shift types to a configuration document for a specific
    company and department. Creates the document if it doesn't exist.
    """
    try:
        # 1. Get and Validate Request Payload
        data = request.get_json()
        try:
            payload = _validate_payload(data)
            department = payload["department"]
            company = payload["company"]
            new_shift_types = payload["new_shift_types"]
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400

        # 2. Fetch Existing Data
        query_filter = {"DEPARTMENT": department, "COMPANY": company}
        existing_doc = mongo.db.configs.find_one(query_filter, {"SHIFT_TYPE.label": 1})

        existing_shift_labels = set()
        if existing_doc and "SHIFT_TYPE" in existing_doc:
            existing_shift_labels = {
                shift["label"] for shift in existing_doc["SHIFT_TYPE"]
            }

        # 3. Collect All Validation Errors
        validation_errors = _collect_validation_errors(
            new_shift_types, existing_shift_labels
        )
        if validation_errors:
            return jsonify({"success": False, "errors": validation_errors}), 400

        # 4. Prepare New Data for Insertion (Add UUIDs)
        shifts_to_add = [
            {**shift, "uuid": str(uuid.uuid4())} for shift in new_shift_types
        ]

        # 5. Update Database Atomically
        result = mongo.db.configs.update_one(
            query_filter,
            {
                "$push": {"SHIFT_TYPE": {"$each": shifts_to_add}},
                "$setOnInsert": {
                    "COMPANY": company,
                    "DEPARTMENT": department,
                    "CONFIG_TYPE": "SHIFT_TYPE",
                },
            },
            upsert=True,
        )

        if result.modified_count > 0 or result.upserted_id is not None:
            return jsonify(
                {"success": True, "message": "New shift types added successfully!"}
            ), 200
        else:
            # This case is unlikely with upsert=True but good for robustness
            raise Exception("Database update failed for an unknown reason.")

    except Exception as e:
        # Generic error handler for unexpected issues
        return jsonify(
            {"success": False, "message": f"An unexpected error occurred: {str(e)}"}
        ), 500


def _validate_update_payload(data):
    """
    Validates that the required fields are present for an update operation.
    """
    if not data:
        raise ValueError("Request body cannot be empty.")

    required_fields = ["COMPANY", "DEPARTMENT", "uuid", "update_data"]
    if not all(field in data for field in required_fields):
        raise ValueError(
            "Missing required fields: COMPANY, DEPARTMENT, uuid, update_data"
        )

    if not isinstance(data["update_data"], dict) or not data["update_data"]:
        raise ValueError(
            "update_data must be a non-empty object with fields to update."
        )

    return {
        "company": data["COMPANY"],
        "department": data["DEPARTMENT"],
        "uuid": data["uuid"],
        "update_data": data["update_data"],
    }


@overall_config_bp.route("/shift_type/update", methods=["POST"])
def update_shift_type():
    """
    Updates a specific shift type within a configuration document,
    identified by its UUID.
    """
    try:
        # 1. Get and Validate Request Payload
        data = request.get_json()
        try:
            payload = _validate_update_payload(data)
            company = payload["company"]
            department = payload["department"]
            shift_uuid = payload["uuid"]
            update_data = payload["update_data"]
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400

        # 2. Find the Relevant Document First
        query_filter = {"COMPANY": company, "DEPARTMENT": department}
        existing_doc = mongo.db.configs.find_one(query_filter)

        if not existing_doc:
            return jsonify(
                {
                    "success": False,
                    "message": "Configuration for the specified company and department not found.",
                }
            ), 404

        # 3. Perform Business Logic Validation (e.g., check for duplicate labels)
        new_label = update_data.get("label")
        if new_label:
            # Check if any *other* shift already has this label
            for shift in existing_doc.get("SHIFT_TYPE", []):
                if shift.get("label") == new_label and shift.get("uuid") != shift_uuid:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Another shift already exists with the label '{new_label}'.",
                        }
                    ), 400

        # 4. Construct the Atomic Update Operation
        # We will build a $set object to update fields of the matched array element.
        # Example: {"SHIFT_TYPE.$.label": "New Label", "SHIFT_TYPE.$.color": "#FFF"}
        update_fields = {
            f"SHIFT_TYPE.$.{key}": value for key, value in update_data.items()
        }

        # The query must now match the specific array element using its UUID
        update_query = {
            "COMPANY": company,
            "DEPARTMENT": department,
            "SHIFT_TYPE.uuid": shift_uuid,
        }

        result = mongo.db.configs.update_one(update_query, {"$set": update_fields})

        # 5. Check Result and Return Response
        if result.modified_count > 0:
            return jsonify(
                {"success": True, "message": "Shift type updated successfully."}
            ), 200
        else:
            # This means the query ran, but no document matched the filter.
            # This happens if the company/dept is correct but the UUID is not found.
            return jsonify(
                {
                    "success": False,
                    "message": "Shift type with the specified UUID not found.",
                }
            ), 404

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"An unexpected error occurred: {str(e)}"}
        ), 500


def _validate_delete_payload(data):
    """
    Validates that the required fields are present for a delete operation.
    """
    if not data:
        raise ValueError("Request body cannot be empty.")

    required_fields = ["COMPANY", "DEPARTMENT", "uuid"]
    if not all(field in data for field in required_fields):
        raise ValueError("Missing required fields: COMPANY, DEPARTMENT, uuid")

    return {
        "company": data["COMPANY"],
        "department": data["DEPARTMENT"],
        "uuid": data["uuid"],
    }


# --- Delete Flask Route ---


@overall_config_bp.route("/shift_type/delete", methods=["POST"])
def delete_shift_type():
    """
    Deletes a specific shift type from a configuration document,
    identified by its UUID.
    """
    try:
        # 1. Get and Validate Request Payload
        data = request.get_json()
        try:
            payload = _validate_delete_payload(data)
            company = payload["company"]
            department = payload["department"]
            shift_uuid = payload["uuid"]
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400

        # 2. Construct and Execute the Atomic Delete Operation
        query_filter = {"COMPANY": company, "DEPARTMENT": department}

        # The $pull operator removes from an existing array all instances
        # of a value or values that match a specified condition.
        update_operation = {"$pull": {"SHIFT_TYPE": {"uuid": shift_uuid}}}

        result = mongo.db.configs.update_one(query_filter, update_operation)

        # 3. Check Result and Return Response
        if result.modified_count > 0:
            return jsonify(
                {"success": True, "message": "Shift type deleted successfully."}
            ), 200
        else:
            # This means no document was modified. This can happen if the
            # company/department doesn't exist, or if the UUID was not found.
            return jsonify(
                {
                    "success": False,
                    "message": "Shift not found or already deleted.",
                }
            ), 404

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"An unexpected error occurred: {str(e)}"}
        ), 500


# @overall_config_bp.route("/shift_type", methods=["POST"])
# def update_shift_type():
#     try:
#         data = request.get_json()

#         if (
#             not data
#             or "DEPARTMENT" not in data
#             or "COMPANY" not in data
#             or "SHIFT_TYPE" not in data
#         ):
#             return jsonify(
#                 {
#                     "success": False,
#                     "message": "Missing required fields: DEPARTMENT, COMPANY, SHIFT_TYPE",
#                 }
#             ), 400

#         department = data["DEPARTMENT"]
#         company = data["COMPANY"]
#         config_type = "SHIFT_TYPE"
#         new_shift_types = data["SHIFT_TYPE"]

#         # Find existing config
#         existing_config = mongo.db.configs.find_one(
#             {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type}
#         )

#         if existing_config:
#             # Get existing shift types
#             existing_shift_types = existing_config.get("SHIFT_TYPE", [])

#             # Create a dictionary for quick lookup by type
#             existing_types_dict = {
#                 shift["type"]: shift for shift in existing_shift_types
#             }

#             # Process new shift types
#             for new_shift in new_shift_types:
#                 shift_type = new_shift.get("type")
#                 if shift_type in existing_types_dict:
#                     # Replace existing shift type
#                     existing_types_dict[shift_type] = new_shift
#                 else:
#                     # Add new shift type
#                     existing_types_dict[shift_type] = new_shift

#             # Convert back to list
#             updated_shift_types = list(existing_types_dict.values())

#             # Update the document
#             mongo.db.configs.update_one(
#                 {
#                     "DEPARTMENT": department,
#                     "COMPANY": company,
#                     "CONFIG_TYPE": config_type,
#                 },
#                 {"$set": {"SHIFT_TYPE": updated_shift_types}},
#             )
#         else:
#             # Create new document
#             new_config = {
#                 "DEPARTMENT": department,
#                 "COMPANY": company,
#                 "CONFIG_TYPE": config_type,
#                 "SHIFT_TYPE": new_shift_types,
#             }
#             mongo.db.configs.insert_one(new_config)

#         # Fetch updated data to return
#         updated_config = mongo.db.configs.find_one(
#             {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
#             {"_id": 0},  # Exclude _id from response
#         )

#         return jsonify(
#             {
#                 "success": True,
#                 "message": "Shift types updated successfully",
#                 "data": updated_config,
#             }
#         ), 200

#     except Exception as e:
#         return jsonify(
#             {"success": False, "message": "Error updating shift types", "error": str(e)}
#         ), 500


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

        # Find all employees and extract unique roles
        employees = mongo.db.employee.find({"DEPARTMENT": department}, {"ROLE": 1})

        # Extract unique roles, filter out None/null values
        roles = set()
        for employee in list(employees):
            if employee.get("ROLE"):
                roles.add(employee["ROLE"])

        # Convert to list and add DEFAULT option
        role_list = sorted(list(roles))
        # role_list.insert(0, "DEFAULT")
        role_set = set(role_list)  # For faster lookup
        print("TEST roles: " + str(role_list))

        existing_config = mongo.db.configs.find_one(
            {"DEPARTMENT": department, "COMPANY": company, "CONFIG_TYPE": config_type},
            {"_id": 0, "CONFIG_TYPE": 0, "DEPARTMENT": 0, "COMPANY": 0},
        )

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
