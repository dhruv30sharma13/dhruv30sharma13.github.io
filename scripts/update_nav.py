#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
CONFIG_PATH = ROOT / "mkdocs.yml"

ROOT_PAGE_ORDER = ("index.md", "technical-blogs/index.md", "contact.md")
ROOT_PAGE_TITLES = {
    "index.md": "Home",
    "technical-blogs/index.md": "Technical Blogs",
    "contact.md": "Contact",
}


def display_name_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def chapter_number_from_segment(segment: str) -> str | None:
    match = re.fullmatch(r"chapter-(\d+(?:\.\d+)*)", segment)
    return match.group(1) if match else None


def numeric_sort_value(number: str) -> str:
    return ".".join(f"{int(part):04d}" for part in number.split("."))


def technical_blog_parts(path: Path) -> tuple[str, ...]:
    rel_parts = path.relative_to(DOCS_DIR).parts
    if not rel_parts or rel_parts[0] != "technical-blogs":
        return ()
    if path.name == "index.md":
        return rel_parts[1:-1]
    return rel_parts[1:-1]


def chapter_path_number(path: Path) -> str | None:
    current: str | None = None
    for segment in technical_blog_parts(path):
        segment_number = chapter_number_from_segment(segment)
        if not segment_number:
            continue

        if current and segment_number.startswith(f"{current}."):
            current = segment_number
        elif current:
            current = f"{current}.{segment_number}"
        else:
            current = segment_number

    return current


def strip_existing_number(title: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\s+", "", title).strip()


def technical_blog_title(path: Path, metadata: dict[str, Any]) -> str | None:
    rel_parts = path.relative_to(DOCS_DIR).parts
    if not rel_parts or rel_parts[0] != "technical-blogs":
        return None

    if path.relative_to(DOCS_DIR).as_posix() == "technical-blogs/index.md":
        return "Technical Blogs"

    if path.name == "index.md":
        chapter_number = chapter_path_number(path)
        if chapter_number and chapter_number_from_segment(path.parent.name):
            return f"Chapter {chapter_number}"
        return display_name_from_slug(path.parent.name)

    base_title = str(metadata.get("title") or display_name_from_slug(path.stem))
    nav_order = metadata.get("nav_order")
    chapter_number = chapter_path_number(path)
    if isinstance(nav_order, int) and chapter_number and chapter_number_from_segment(path.parent.name):
        return f"{chapter_number}.{nav_order} {strip_existing_number(base_title)}"

    return base_title


def front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}

    _, metadata, _ = text.split("---", 2)
    loaded = yaml.safe_load(metadata) or {}
    return loaded if isinstance(loaded, dict) else {}


def title_for(path: Path) -> str:
    rel = path.relative_to(DOCS_DIR).as_posix()
    metadata = front_matter(path)
    blog_title = technical_blog_title(path, metadata)
    if blog_title:
        return blog_title
    if metadata.get("nav_title"):
        return str(metadata["nav_title"])
    if rel in ROOT_PAGE_TITLES:
        return ROOT_PAGE_TITLES[rel]
    if metadata.get("title"):
        return str(metadata["title"])
    stem = path.parent.name if path.name == "index.md" else path.stem
    return display_name_from_slug(stem)


def html_url(md_rel: str) -> str:
    path = Path(md_rel)
    if path.name == "index.md":
        if path.parent == Path("."):
            return "index.html"
        return f"{path.parent.as_posix()}/index.html"
    return f"{path.with_suffix('').as_posix()}.html"


def sort_key(path: Path) -> tuple[int, str, str]:
    rel = path.relative_to(DOCS_DIR).as_posix()
    metadata = front_matter(path)
    if rel in ROOT_PAGE_ORDER:
        return (ROOT_PAGE_ORDER.index(rel), "", rel)
    if rel.startswith("technical-blogs/") and path.name == "index.md":
        chapter_number = chapter_path_number(path)
        if chapter_number and chapter_number_from_segment(path.parent.name):
            return (10, numeric_sort_value(chapter_number), rel)
    if path.name == "index.md":
        return (10, rel, rel)
    nav_order = metadata.get("nav_order")
    if isinstance(nav_order, int):
        return (20, f"{nav_order:04d}", rel)
    return (30, rel, rel)


def child_pages(directory: Path) -> list[Path]:
    children: list[Path] = []

    for child_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
        index = child_dir / "index.md"
        if index.exists():
            children.append(index)

    for child_file in sorted(p for p in directory.glob("*.md") if p.name != "index.md"):
        children.append(child_file)

    return sorted(children, key=sort_key)


def nav_for_directory(directory: Path, include_index: bool = True) -> list[Any]:
    items: list[Any] = []
    index = directory / "index.md"

    if include_index and index.exists():
        rel = index.relative_to(DOCS_DIR).as_posix()
        items.append({title_for(index): rel})

    for child in child_pages(directory):
        if child == index:
            continue

        if child.name == "index.md":
            rel = child.relative_to(DOCS_DIR).as_posix()
            nested = nav_for_directory(child.parent, include_index=False)
            if nested:
                items.append({title_for(child): [{title_for(child): rel}, *nested]})
            else:
                items.append({title_for(child): rel})
        else:
            rel = child.relative_to(DOCS_DIR).as_posix()
            items.append({title_for(child): rel})

    return items


def nav_tree() -> list[Any]:
    items: list[Any] = []

    for rel in ROOT_PAGE_ORDER:
        path = DOCS_DIR / rel
        if not path.exists():
            continue

        if path.name == "index.md" and path.parent != DOCS_DIR:
            nested = nav_for_directory(path.parent, include_index=False)
            items.append({title_for(path): [{title_for(path): rel}, *nested]})
        else:
            items.append({title_for(path): rel})

    seen = nav_paths(items)
    for path in sorted(DOCS_DIR.rglob("*.md"), key=sort_key):
        rel = path.relative_to(DOCS_DIR).as_posix()
        if rel in seen:
            continue
        if path.name == "index.md" and path.parent != DOCS_DIR:
            nested = [{title_for(path): rel}, *nav_for_directory(path.parent, include_index=False)]
            items.append({title_for(path): nested})
            seen.update(nav_paths([{title_for(path): nested}]))
        else:
            items.append({title_for(path): rel})
            seen.add(rel)

    return items


def nav_paths(items: list[Any]) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, str):
            paths.add(item)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.add(value)
                elif isinstance(value, list):
                    paths.update(nav_paths(value))
    return paths


def page_url(path: Path) -> str:
    return html_url(path.relative_to(DOCS_DIR).as_posix())


def page_link(path: Path) -> dict[str, str]:
    return {
        "title": title_for(path),
        "url": page_url(path),
        "src": path.relative_to(DOCS_DIR).as_posix(),
    }


def page_tree(path: Path) -> dict[str, Any]:
    link: dict[str, Any] = page_link(path)
    if path.name == "index.md":
        children = [page_tree(child) for child in child_pages(path.parent) if child != path]
        if children:
            link["children"] = children
    return link


def strip_label_for(path: Path) -> str:
    rel_parts = path.relative_to(DOCS_DIR).parts
    if not rel_parts or rel_parts[0] != "technical-blogs":
        return title_for(path)

    labels = ["Technical Blogs"]
    if len(rel_parts) == 1:
        return labels[0]

    chapter_parts = rel_parts[1:-1] if path.name != "index.md" else rel_parts[1:-1]
    if path.name == "index.md" and len(rel_parts) > 2:
        chapter_parts = rel_parts[1:-1]

    current_number: str | None = None
    for segment in chapter_parts:
        segment_number = chapter_number_from_segment(segment)
        if segment_number:
            if current_number and segment_number.startswith(f"{current_number}."):
                current_number = segment_number
            elif current_number:
                current_number = f"{current_number}.{segment_number}"
            else:
                current_number = segment_number
            labels.append(f"Chapter {current_number}")
        else:
            labels.append(display_name_from_slug(segment))

    if path.name == "index.md" and path.parent.name != "technical-blogs":
        current_number = chapter_path_number(path)
        current_label = (
            f"Chapter {current_number}"
            if current_number and chapter_number_from_segment(path.parent.name)
            else display_name_from_slug(path.parent.name)
        )
        if labels[-1] != current_label:
            labels.append(current_label)

    return " / ".join(labels)


def parent_page(path: Path) -> Path | None:
    if path.name != "index.md":
        candidate = path.parent / "index.md"
        return candidate if candidate.exists() and candidate != path else None

    if path.parent == DOCS_DIR:
        return None

    candidate = path.parent.parent / "index.md"
    return candidate if candidate.exists() else None


def generated_titles() -> dict[str, str]:
    return {
        path.relative_to(DOCS_DIR).as_posix(): title_for(path)
        for path in sorted(DOCS_DIR.rglob("*.md"))
    }


def generated_strip_labels() -> dict[str, str]:
    return {
        path.relative_to(DOCS_DIR).as_posix(): strip_label_for(path)
        for path in sorted(DOCS_DIR.rglob("*.md"))
    }


def chapter_page(path: Path) -> Path | None:
    rel_parts = path.relative_to(DOCS_DIR).parts
    if len(rel_parts) < 3 or rel_parts[0] != "technical-blogs":
        return None

    candidate = DOCS_DIR / rel_parts[0] / rel_parts[1] / "index.md"
    return candidate if candidate.exists() else None


def page_links() -> dict[str, Any]:
    links: dict[str, Any] = {}

    for path in sorted(DOCS_DIR.rglob("*.md")):
        rel = path.relative_to(DOCS_DIR).as_posix()
        entry: dict[str, Any] = {}

        if rel != "index.md":
            entry["home"] = {"title": "Home", "url": "index.html"}

        parent = parent_page(path)
        if parent:
            entry["parent"] = page_link(parent)

        chapter = chapter_page(path)
        if chapter and chapter != path:
            entry["chapter"] = page_link(chapter)

        if path.name == "index.md":
            children = child_pages(path.parent)
            child_links = [page_tree(child) for child in children if child != path]
            if child_links:
                entry["children"] = child_links

        links[rel] = entry

    return links


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    extra = config.setdefault("extra", {})
    extra.setdefault("owner_name", config.get("site_name", "Site"))
    extra["footer_links"] = [
        {"title": "Home", "url": "index.html"},
        {"title": "Technical Blogs", "url": "technical-blogs/index.html"},
        {"title": "Contact", "url": "contact.html"},
    ]
    extra["page_links"] = page_links()
    extra["generated_titles"] = generated_titles()
    extra["generated_strip_labels"] = generated_strip_labels()
    config["nav"] = nav_tree()

    CONFIG_PATH.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
