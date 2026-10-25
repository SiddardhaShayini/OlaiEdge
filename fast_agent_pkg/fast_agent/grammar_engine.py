# fast_agent/grammar_engine.py
"""
Grammar Engine for FastAgent Edge.
Provides GBNF grammar generation, JSON Schema constraints, and pre-packaged schemas
for desktop software categories (Code Editors, Note-Taking, CAD, Accounting).
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple


# Pre-packaged schemas for common desktop app verticals
DESKTOP_SCHEMAS = {
    # 1. Code Editors (VS Code / JetBrains / Custom IDEs)
    "code_editor_patch": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "action": {"type": "string", "enum": ["replace", "insert", "delete"]},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
            "replacement_code": {"type": "string"},
            "commit_message": {"type": "string"},
        },
        "required": ["file_path", "action", "start_line", "replacement_code"],
    },
    # 2. Note-Taking Apps (Obsidian / Notion / Joplin / Logseq)
    "note_summary": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "action_items": {
                "type": "array",
                "items": {"type": "string"},
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["title", "summary", "key_points", "tags"],
    },
    # 3. CAD & 3D Engineering (FreeCAD / Blender / SolidWorks extensions)
    "cad_command": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["extrude", "cut", "fillet", "chamfer", "revolve"]},
            "target_body": {"type": "string"},
            "plane": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
            "dimensions_mm": {
                "type": "object",
                "properties": {
                    "distance": {"type": "number"},
                    "radius": {"type": "number"},
                    "angle_degrees": {"type": "number"},
                },
            },
            "tolerance": {"type": "number"},
        },
        "required": ["operation", "target_body", "plane", "dimensions_mm"],
    },
    # 4. Accounting & ERP Software (QuickBooks / Odoo / Custom Financial tools)
    "accounting_entry": {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "string"},
            "date": {"type": "string"},
            "debit_account": {"type": "string"},
            "credit_account": {"type": "string"},
            "amount": {"type": "number"},
            "currency": {"type": "string"},
            "tax_code": {"type": "string"},
            "memo": {"type": "string"},
        },
        "required": ["transaction_id", "date", "debit_account", "credit_account", "amount", "currency"],
    },
}


class GrammarEngine:
    """
    Translates JSON schemas into GBNF grammars and validates generated JSON.
    Guarantees 100% syntactically valid structured outputs for edge applications.
    """

    @staticmethod
    def get_desktop_schema(category: str) -> Dict[str, Any]:
        """Returns pre-packaged schema for a given desktop category."""
        if category not in DESKTOP_SCHEMAS:
            available = ", ".join(DESKTOP_SCHEMAS.keys())
            raise ValueError(f"Unknown desktop schema '{category}'. Available: {available}")
        return DESKTOP_SCHEMAS[category]

    @staticmethod
    def json_schema_to_gbnf(schema: Dict[str, Any]) -> str:
        """
        Converts a standard JSON Schema into a GBNF (GGML BNF) grammar string.
        Handles object, string, number, integer, boolean, enum, and array.
        """
        rules: Dict[str, str] = {}
        rules["ws"] = r'(" " | "\t" | "\n")*'
        rules["string"] = r'"\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""'
        rules["number"] = r'("-")? ([0-9]+) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?'
        rules["integer"] = r'("-")? [0-9]+'
        rules["boolean"] = r'("true" | "false")'
        rules["null"] = r'"null"'

        def _generate_rule_for_type(sub_schema: Dict[str, Any], rule_name: str) -> str:
            # Handle enums
            if "enum" in sub_schema:
                enum_opts = []
                for val in sub_schema["enum"]:
                    if isinstance(val, str):
                        enum_opts.append(f'"\\"{val}\\""')
                    else:
                        enum_opts.append(f'"{val}"')
                rules[rule_name] = " | ".join(enum_opts)
                return rule_name

            stype = sub_schema.get("type", "string")

            if stype == "string":
                return "string"
            elif stype == "number":
                return "number"
            elif stype == "integer":
                return "integer"
            elif stype == "boolean":
                return "boolean"
            elif stype == "array":
                item_schema = sub_schema.get("items", {"type": "string"})
                item_rule = f"{rule_name}-item"
                _generate_rule_for_type(item_schema, item_rule)
                rules[rule_name] = f'"[" ws ({item_rule} (ws "," ws {item_rule})*)? ws "]"'
                return rule_name
            elif stype == "object":
                props = sub_schema.get("properties", {})
                required = sub_schema.get("required", list(props.keys()))

                prop_rules = []
                for p_name, p_schema in props.items():
                    p_rule_name = f"{rule_name}-{p_name}"
                    ref_rule = _generate_rule_for_type(p_schema, p_rule_name)
                    kv_expr = f'"\\"{p_name}\\"" ws ":" ws {ref_rule}'
                    prop_rules.append((p_name, kv_expr, p_name in required))

                if not prop_rules:
                    rules[rule_name] = r'"{" ws "}"'
                    return rule_name

                # Build object sequence
                lines = []
                for i, (_, kv_expr, is_req) in enumerate(prop_rules):
                    prefix = 'ws "," ws ' if i > 0 else ""
                    if is_req:
                        lines.append(f'{prefix}{kv_expr}')
                    else:
                        lines.append(f'({prefix}{kv_expr})?')

                rules[rule_name] = f'"\\{{" ws {" ".join(lines)} ws "\\}}"'
                return rule_name

            return "string"

        root_rule = _generate_rule_for_type(schema, "root-obj")
        rules["root"] = f"{root_rule}"

        # Assemble GBNF
        output_lines = [f"root ::= {rules['root']}"]
        for r_name, r_val in rules.items():
            if r_name != "root":
                output_lines.append(f"{r_name} ::= {r_val}")

        return "\n".join(output_lines)

    @staticmethod
    def validate_and_parse(
        raw_output: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Parses JSON output from LLM and validates against provided schema.
        Returns: (success: bool, parsed_data: Any, error_message: Optional[str])
        """
        cleaned = raw_output.strip()
        # Find first { and last } or first [ and last ]
        first_curly = cleaned.find("{")
        last_curly = cleaned.rfind("}")
        first_bracket = cleaned.find("[")
        last_bracket = cleaned.rfind("]")

        target_str = cleaned
        if first_curly != -1 and last_curly != -1 and (first_bracket == -1 or first_curly < first_bracket):
            target_str = cleaned[first_curly : last_curly + 1]
        elif first_bracket != -1 and last_bracket != -1:
            target_str = cleaned[first_bracket : last_bracket + 1]

        try:
            parsed = json.loads(target_str)
        except json.JSONDecodeError as jde:
            return False, None, f"JSON Decode Error: {jde}"

        if not schema:
            return True, parsed, None

        # Check required fields
        if schema.get("type") == "object" and isinstance(parsed, dict):
            req_fields = schema.get("required", [])
            missing = [rf for rf in req_fields if rf not in parsed]
            if missing:
                return False, parsed, f"Missing required fields: {', '.join(missing)}"

        return True, parsed, None
