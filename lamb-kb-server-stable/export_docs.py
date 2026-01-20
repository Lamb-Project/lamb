#!/usr/bin/env python3
"""
Export FastAPI OpenAPI documentation to a markdown file.

This script extracts the OpenAPI schema from the FastAPI application
and converts it into a readable markdown document.
"""

import json
import sys
from pathlib import Path

# Import the FastAPI app
from main import app


def get_openapi_schema():
    """Get the OpenAPI schema from the FastAPI app."""
    return app.openapi()


def format_schema_as_markdown(schema):
    """Convert OpenAPI schema to markdown format."""
    md_lines = []
    
    # Title and description
    md_lines.append(f"# {schema['info']['title']} Documentation")
    md_lines.append(f"Version: {schema['info']['version']}\n")
    md_lines.append(f"{schema['info']['description']}\n")
    
    # Base URL
    md_lines.append("## Base URL")
    md_lines.append(f"http://localhost:9090\n")
    
    # Authentication
    md_lines.append("## Authentication")
    md_lines.append("All authenticated endpoints require a Bearer token for authentication. " +
                   "The token must match the `LAMB_API_KEY` environment variable.\n")
    md_lines.append("```bash")
    md_lines.append("Authorization: Bearer 0p3n-w3bu!")
    md_lines.append("```\n")
    
    # Endpoints by tag
    tags_dict = {tag["name"]: tag["description"] if "description" in tag else "" 
                for tag in schema.get("tags", [])}
    
    paths_by_tag = {}
    
    # Group paths by tag
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if "tags" in operation and operation["tags"]:
                tag = operation["tags"][0]
                if tag not in paths_by_tag:
                    paths_by_tag[tag] = []
                paths_by_tag[tag].append((path, method, operation))
    
    # Order tags as they appear in paths
    ordered_tags = list(paths_by_tag.keys())
    
    # Generate documentation for each tag
    for tag in ordered_tags:
        md_lines.append(f"## {tag}")
        if tag in tags_dict and tags_dict[tag]:
            md_lines.append(f"{tags_dict[tag]}\n")
        
        # Document each endpoint
        for path, method, operation in paths_by_tag[tag]:
            method_upper = method.upper()
            summary = operation.get("summary", "")
            md_lines.append(f"### {summary}")
            md_lines.append(f"**{method_upper}** `{path}`\n")
            
            if "description" in operation:
                md_lines.append(operation["description"])
                md_lines.append("")
            
            # Parameters
            if "parameters" in operation and operation["parameters"]:
                md_lines.append("#### Parameters")
                md_lines.append("| Name | In | Type | Required | Description |")
                md_lines.append("| ---- | -- | ---- | -------- | ----------- |")
                
                for param in operation["parameters"]:
                    name = param.get("name", "")
                    param_in = param.get("in", "")
                    required = "Yes" if param.get("required", False) else "No"
                    description = param.get("description", "").replace("\n", " ")
                    
                    # Get type from schema if available
                    param_type = "string"  # default
                    if "schema" in param and "type" in param["schema"]:
                        param_type = param["schema"]["type"]
                    
                    md_lines.append(f"| {name} | {param_in} | {param_type} | {required} | {description} |")
                
                md_lines.append("")
            
            # Request body
            if "requestBody" in operation:
                md_lines.append("#### Request Body")
                content = operation["requestBody"].get("content", {})
                for content_type, content_schema in content.items():
                    md_lines.append(f"Content-Type: `{content_type}`\n")
                    if "schema" in content_schema:
                        schema_ref = content_schema["schema"]
                        if "$ref" in schema_ref:
                            ref_name = schema_ref["$ref"].split("/")[-1]
                            md_lines.append(f"Schema: `{ref_name}`\n")
                
                # Example from description if it contains a curl command
                if "description" in operation and "```bash" in operation["description"]:
                    example_start = operation["description"].find("```bash")
                    example_end = operation["description"].find("```", example_start + 7)
                    if example_start > -1 and example_end > -1:
                        example = operation["description"][example_start:example_end + 3]
                        md_lines.append("Example:")
                        md_lines.append(example)
                        md_lines.append("")
            
            # Responses
            if "responses" in operation:
                md_lines.append("#### Responses")
                for status_code, response in operation["responses"].items():
                    md_lines.append(f"**{status_code}**: {response.get('description', '')}")
                    
                    if "content" in response:
                        for content_type, content_schema in response["content"].items():
                            md_lines.append(f"Content-Type: `{content_type}`")
                    
                    md_lines.append("")
            
            md_lines.append("---\n")
    
    # Schemas
    md_lines.append("## Models")
    
    if "components" in schema and "schemas" in schema["components"]:
        for schema_name, schema_obj in schema["components"]["schemas"].items():
            md_lines.append(f"### {schema_name}")
            
            if "description" in schema_obj:
                md_lines.append(schema_obj["description"])
            
            if "properties" in schema_obj:
                md_lines.append("\n#### Properties")
                md_lines.append("| Name | Type | Description |")
                md_lines.append("| ---- | ---- | ----------- |")
                
                for prop_name, prop in schema_obj["properties"].items():
                    prop_type = prop.get("type", "object")
                    description = prop.get("description", "").replace("\n", " ")
                    
                    # Handle references
                    if "$ref" in prop:
                        ref_name = prop["$ref"].split("/")[-1]
                        prop_type = f"[{ref_name}](#{ref_name.lower()})"
                    
                    md_lines.append(f"| {prop_name} | {prop_type} | {description} |")
                
                md_lines.append("")
            
            md_lines.append("---\n")
    
    return "\n".join(md_lines)


def main():
    """Main function to export OpenAPI schema to markdown."""
    output_path = Path("../Docs/api_documentation.md")
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
    
    schema = get_openapi_schema()
    markdown = format_schema_as_markdown(schema)
    
    # Save to file
    with open(output_path, "w") as f:
        f.write(markdown)
    
    print(f"Documentation exported to {output_path}")


if __name__ == "__main__":
    main()
