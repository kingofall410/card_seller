import os
from bs4 import BeautifulSoup
from collections import defaultdict
from urllib.parse import urljoin

def generate_html_table(sorted_items, original_img_path=None, cropped_img_path=None, classified_words=None):
    html = """<html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
            .preview-container { display: flex; gap: 30px; align-items: stretch; margin-bottom: 20px; }
            .preview-block { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: stretch; }
            .preview-img-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; width: 100%; }
            .preview-block img { max-height: 100%; max-width: 100%; object-fit: contain; border: 1px solid #ccc; }
            .preview-caption { text-align: center; font-size: 14px; margin-top: 6px; }
            .form-block { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 250px; }
            .form-block form { display: flex; flex-direction: column; gap: 10px; flex: 1; }
            input, textarea { border: 1px solid #ccc; padding: 6px; width: 100%; }
        </style>
    </head>
    <body>"""

    if classified_words or original_img_path or cropped_img_path:
        html += '<div class="preview-container">\n'

        if original_img_path:
            html += f"""
                <div class="preview-block">
                    <div class="preview-img-wrapper">
                        <img src="{original_img_path}">
                    </div>
                    <div class="preview-caption">Original</div>
                </div>
            """

        if cropped_img_path:
            html += f"""
                <div class="preview-block">
                    <div class="preview-img-wrapper">
                        <img src="{cropped_img_path}">
                    </div>
                    <div class="preview-caption">Cropped</div>
                </div>
            """

        if classified_words:
            html += '<div class="form-block">'
            html += '<h4 style="margin: 0 0 10px 0;">🧠 Classified Words</h4>'
            html += '<form>'

            unknown_words = []

            for label, word in classified_words.items():
                if label == "unknown":
                    unknown_words.extend(word)
                    continue

                # Now we expect every value to be a (text, percent) tuple
                values = word if isinstance(word, list) else [word]

                for text, pct in values:
                    suffix = f" ({pct}%)"
                    html += f'''
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label style="min-width: 80px; font-weight: bold;">{label}</label>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <input type="text" value="{text}" readonly style="flex: 1;">
                                <span style="min-width: 60px;">{pct}%</span>
                            </div>

                        </div>
                    '''


            if unknown_words:
                html += f'''
                    <div>
                        <label style="font-weight: bold;">Unknown Words</label>
                        <textarea rows="2" readonly>{' '.join(str(w) for w in unknown_words)}</textarea>

                    </div>
                '''

            html += '</form></div>'  # close form-block

        html += '</div>'  # close preview-container

    html += """
        <h2>Top Matches Sorted by Hue Similarity</h2>
        <table>
            <tr>
                <th>#</th>
                <th>Thumbnail</th>
                <th>Title</th>
                <th>Hue</th>
                <th>Δ Hue</th>
            </tr>"""

    for idx, item in enumerate(sorted_items, 1):
        title = item.get("title", "No title")
        thumb_url = item.get("thumbnailImages", [{}])[0].get("imageUrl", "")
        hue = f"{item.get('thumbHue', 0):.2f}"
        delta = f"{item.get('hueDistance', 0):.2f}"
        html += f"""
            <tr>
                <td>{idx}</td>
                <td><img src="{thumb_url}" alt="Thumbnail" style="max-height: 100px;"></td>
                <td>{title}</td>
                <td>{hue}</td>
                <td>{delta}</td>
            </tr>"""

    html += "</table></body></html>"
    return html

import os
from collections import defaultdict
from bs4 import BeautifulSoup
from django.template.loader import render_to_string


def generate_index_from_directory(directory):
    preview_blocks = []
    print("here:", directory)
    for file in sorted(os.listdir(directory)):
        if not file.endswith(".html") or file == "index.html":
            continue

        file_path = os.path.join(directory, file)
        with open(file_path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        previews = soup.find_all("img")
        #original_img = "/"+os.path.join(directory, os.path.basename(previews[0].get("src") if len(previews) > 0 else "")).replace("\\", "/")
        original_img = "/media/uploaded_run/" + os.path.basename(previews[0].get("src") or "")
        cropped_img = "/media/uploaded_run/" + os.path.basename(previews[0].get("src") or "")
        print(original_img)
        label_map = defaultdict(list)

        for div in soup.select("form div"):
            label_tag = div.find("label")
            if not label_tag:
                continue
            label = label_tag.get_text(strip=True).lower()

            input_tags = div.find_all("input")
            percent_tags = div.find_all("span")
            for i, input_tag in enumerate(input_tags):
                val = input_tag.get("value", "").strip()
                pct = percent_tags[i].get_text(strip=True).replace("%", "") if i < len(percent_tags) else ""
                label_map[label].append((val, pct))

            textarea = div.find("textarea")
            if textarea:
                for word in textarea.get_text(strip=True).split():
                    label_map[label].append((word, ""))

        def label_row(label):
            entries = label_map.get(label.lower(), [])
            if not entries:
                return ""
            rowspan = len(entries)
            rows = []
            for i, (val, pct) in enumerate(entries):
                if i == 0:
                    rows.append(f"<tr><td rowspan='{rowspan}'><b>{label.title()}</b></td><td>{val}</td><td>{pct}</td></tr>")
                else:
                    rows.append(f"<tr><td>{val}</td><td>{pct}</td></tr>")
            return "\n".join(rows)

        label_rows = "\n".join([
            label_row("first_name"),
            label_row("last_name"),
            label_row("year"),
            label_row("card_number"),
            label_row("brand"),
            label_row("team"),
            label_row("city"),
            label_row("title_similarity"),
            label_row("attributes"),
            label_row("subset"),
            label_row("unknown words"),
        ])

        function_id = file.replace(".", "_")
        '''export_script = render_to_string("export_script.js", {
            "function_id": function_id,
            "label_map": label_map,
            "filename": file
        })'''
        print(f"Rendering: {file} with original_img={original_img}, cropped_img={cropped_img}")

        preview_block_html = render_to_string("preview_block.html", {
            "original_img": original_img,
            "cropped_img": cropped_img,
            "label_rows": label_rows,
            "function_id": function_id,
            "file": file,
            "export_script": "-",
        })

        preview_blocks.append(preview_block_html)
        print(f"Generated preview block for {file}")

    print(f"Total preview blocks: {len(preview_blocks)}")

    full_html = render_to_string("index.html", {
        "preview_blocks": preview_blocks
    })
    
    with open(os.path.join(directory, "index.html"), "w", encoding="utf-8") as f:
        
        f.write(full_html)