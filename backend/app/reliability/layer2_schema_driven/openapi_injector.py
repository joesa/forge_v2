from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def generate_openapi_spec(
    comprehensive_plan: dict,
    model_defs: list[dict] | None = None,
) -> dict:
    """Generate OpenAPI 3.1 spec from the comprehensive plan and model definitions.

    Injected into APIAgent context before Stage 4.
    If model_defs are provided, generates real request/response schemas with $ref.
    """
    cpo = comprehensive_plan.get("cpo", {})
    user_stories = cpo.get("user_stories", [])

    # Derive resource names from user stories
    resources: list[str] = []
    for story in user_stories:
        title = story.get("title", "").lower()
        for word in ["create", "view", "edit", "delete", "list", "search", "update"]:
            title = title.replace(word, "").strip()
        if title and title not in resources:
            resources.append(title)

    # Build component schemas from model_defs
    schemas: dict[str, dict] = {}
    model_names = set()
    if model_defs:
        for model in model_defs:
            name = model.get("name", "Unknown")
            model_names.add(name)
            properties: dict[str, dict] = {}
            required: list[str] = []
            for field in model.get("fields", []):
                fname = field["name"]
                ftype = field.get("type", "str")
                prop = _python_type_to_openapi(ftype)
                properties[fname] = prop
                if field.get("required", True):
                    required.append(fname)
            schema: dict = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            schemas[name] = schema

            # Create/Update schema — same but without id and timestamps
            create_props = {
                k: v for k, v in properties.items()
                if k not in ("id", "created_at", "updated_at")
            }
            create_required = [r for r in required if r not in ("id", "created_at", "updated_at")]
            create_schema: dict = {"type": "object", "properties": create_props}
            if create_required:
                create_schema["required"] = create_required
            schemas[f"{name}Create"] = create_schema

    # Build paths
    paths: dict[str, dict] = {}
    for resource in resources[:10]:
        slug = resource.replace(" ", "_").lower()
        class_name = resource.replace(" ", "").title()

        # Try to match resource to a model schema
        matched_model = _match_resource_to_model(class_name, model_names)

        list_path: dict = {}
        detail_path: dict = {}

        if matched_model:
            ref = f"#/components/schemas/{matched_model}"
            create_ref = f"#/components/schemas/{matched_model}Create"

            list_path = {
                "get": {
                    "summary": f"List {resource}",
                    "operationId": f"list_{slug}",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}},
                        {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                    ],
                    "responses": {
                        "200": {
                            "description": f"List of {resource}",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"$ref": ref}},
                                },
                            },
                        },
                    },
                },
                "post": {
                    "summary": f"Create {resource}",
                    "operationId": f"create_{slug}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": create_ref},
                            },
                        },
                    },
                    "responses": {
                        "201": {
                            "description": f"{resource} created",
                            "content": {
                                "application/json": {"schema": {"$ref": ref}},
                            },
                        },
                        "422": {"description": "Validation error"},
                    },
                },
            }
            detail_path = {
                "get": {
                    "summary": f"Get {resource}",
                    "operationId": f"get_{slug}",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
                    "responses": {
                        "200": {
                            "description": f"Single {resource}",
                            "content": {
                                "application/json": {"schema": {"$ref": ref}},
                            },
                        },
                        "404": {"description": "Not found"},
                    },
                },
                "put": {
                    "summary": f"Update {resource}",
                    "operationId": f"update_{slug}",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": create_ref}},
                        },
                    },
                    "responses": {
                        "200": {
                            "description": f"{resource} updated",
                            "content": {
                                "application/json": {"schema": {"$ref": ref}},
                            },
                        },
                        "404": {"description": "Not found"},
                        "422": {"description": "Validation error"},
                    },
                },
                "delete": {
                    "summary": f"Delete {resource}",
                    "operationId": f"delete_{slug}",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}],
                    "responses": {
                        "204": {"description": f"{resource} deleted"},
                        "404": {"description": "Not found"},
                    },
                },
            }
        else:
            # No model matched — generate basic paths without schemas
            list_path = {
                "get": {
                    "summary": f"List {resource}",
                    "operationId": f"list_{slug}",
                    "responses": {"200": {"description": f"List of {resource}"}},
                },
                "post": {
                    "summary": f"Create {resource}",
                    "operationId": f"create_{slug}",
                    "responses": {"201": {"description": f"{resource} created"}},
                },
            }
            detail_path = {
                "get": {
                    "summary": f"Get {resource}",
                    "operationId": f"get_{slug}",
                    "responses": {"200": {"description": f"Single {resource}"}},
                },
                "put": {
                    "summary": f"Update {resource}",
                    "operationId": f"update_{slug}",
                    "responses": {"200": {"description": f"{resource} updated"}},
                },
                "delete": {
                    "summary": f"Delete {resource}",
                    "operationId": f"delete_{slug}",
                    "responses": {"204": {"description": f"{resource} deleted"}},
                },
            }

        paths[f"/api/{slug}"] = list_path
        paths[f"/api/{slug}/{{id}}"] = detail_path

    components: dict = {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
    }
    if schemas:
        components["schemas"] = schemas

    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "Generated API",
            "version": "0.1.0",
        },
        "paths": paths,
        "components": components,
        "security": [{"bearerAuth": []}],
    }

    logger.info(
        "Generated OpenAPI spec with %d paths, %d schemas",
        len(paths), len(schemas),
    )
    return spec


def _match_resource_to_model(resource_name: str, model_names: set[str]) -> str | None:
    """Try to match a resource name to a model schema name."""
    # Exact match
    if resource_name in model_names:
        return resource_name
    # Case-insensitive
    for name in model_names:
        if name.lower() == resource_name.lower():
            return name
    # Singular/plural fuzzy
    for name in model_names:
        if name.lower().rstrip("s") == resource_name.lower().rstrip("s"):
            return name
    return None


_OPENAPI_TYPE_MAP: dict[str, dict] = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "float": {"type": "number"},
    "bool": {"type": "boolean"},
    "datetime": {"type": "string", "format": "date-time"},
    "date": {"type": "string", "format": "date"},
    "uuid": {"type": "string", "format": "uuid"},
    "dict": {"type": "object"},
    "list": {"type": "array", "items": {}},
    "Any": {},
}


def _python_type_to_openapi(python_type: str) -> dict:
    """Convert a Python type string to an OpenAPI schema object."""
    # Handle Optional[X]
    if python_type.startswith("Optional[") and python_type.endswith("]"):
        inner = python_type[9:-1]
        base = _OPENAPI_TYPE_MAP.get(inner, {"type": "string"}).copy()
        base["nullable"] = True
        return base

    # Handle X | None
    if " | None" in python_type:
        inner = python_type.replace(" | None", "").strip()
        base = _OPENAPI_TYPE_MAP.get(inner, {"type": "string"}).copy()
        base["nullable"] = True
        return base

    return _OPENAPI_TYPE_MAP.get(python_type, {"type": "string"}).copy()


def openapi_to_yaml(spec: dict) -> str:
    """Convert OpenAPI spec dict to JSON string (YAML requires pyyaml)."""
    return json.dumps(spec, indent=2, sort_keys=True)
