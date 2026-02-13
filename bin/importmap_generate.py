#!/usr/bin/env python
import json
from pathlib import Path


def generate_import_map(base_dirs):
    import_map = {"imports": {}}
    for base_dir in base_dirs:
        base_path = Path(base_dir)
        # Strip "chat_client" or any top-level prefix.
        relative_dir = str(base_path).split("chat_client/")[-1]
        import_dir = f"/{relative_dir}"

        js_files = sorted(base_path.rglob("*.js"))
        for js_file in js_files:
            relative_js_path = js_file.relative_to(base_path).as_posix()
            key = f"{import_dir}/{relative_js_path}"
            value = key + "?version={{ version }}"
            import_map["imports"][key] = value
    return json.dumps(import_map, indent=4)


base_directories = ["chat_client/static/js", "chat_client/static/dist"]
import_map = generate_import_map(base_directories)
import_map_html = f'<script type="importmap">\n{import_map}\n</script>'

with open("chat_client/templates/includes/importmap.html", "w") as f:
    f.write(import_map_html)
