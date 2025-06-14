#!/usr/bin/env python
import os
import json


def generate_import_map(base_dirs):
    import_map = {"imports": {}}
    for base_dir in base_dirs:
        # Strip "chat_client" or any top-level prefix
        relative_dir = base_dir.split("chat_client/")[-1]  # removes "chat_client/"
        import_dir = f"/{relative_dir}"  # ensures leading slash

        js_files = [f for f in os.listdir(base_dir) if f.endswith(".js")]
        for js_file in js_files:
            key = f"{import_dir}/{js_file}"
            value = key + "?version={{ version }}"
            import_map["imports"][key] = value
    return json.dumps(import_map, indent=4)


base_directories = ["chat_client/static/js", "chat_client/static/dist"]
import_map = generate_import_map(base_directories)
import_map_html = f'<script type="importmap">\n{import_map}\n</script>'

with open("chat_client/templates/includes/importmap.html", "w") as f:
    f.write(import_map_html)
