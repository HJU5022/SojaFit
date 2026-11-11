"""Docling 제목과 같은 페이지의 그림으로 공식 패키지 외형 페이지를 색인한다."""
import argparse
import json
import re
from pathlib import Path
from typing import TypedDict

from backend.rag.source_metadata import official_basename


OUTLINE = re.compile(
    r'\b(?:PACKAGE\s+OUTLINE|OUTLINE\s+DIMENSIONS?|PACKAGE\s+DIMENSIONS?|DIMENSIONS?)\b', re.I,
)


class OutlineRecord(TypedDict):
    source_url: str
    outline_page: int
    heading: str


def read_manifest(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        url = json.loads(line)['source_url']
        name = official_basename(url)
        if name.casefold() in {key.casefold() for key in result}:
            raise ValueError(f'duplicate manifest basename: {name}')
        result[name] = url
    return result


def _pages(item: dict) -> set[int]:
    return {prov['page_no'] for prov in item.get('prov', [])
            if type(prov.get('page_no')) is int and prov['page_no'] >= 1}


def build_outline_index(docling_dir: Path, manifest_path: Path) -> dict[str, OutlineRecord]:
    manifest = {name.casefold(): (name, url) for name, url in read_manifest(manifest_path).items()}
    documents = {}
    for path in sorted(docling_dir.glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        name = doc.get('origin', {}).get('filename')
        if not isinstance(name, str) or not name:
            raise ValueError(f'missing Docling origin.filename: {path.name}')
        key = name.casefold()
        if key in documents:
            raise ValueError(f'duplicate Docling basename: {name}')
        documents[key] = doc
    if missing := set(manifest) - set(documents):
        raise ValueError(f'missing Docling document: {sorted(manifest[key][0] for key in missing)}')
    if extra := set(documents) - set(manifest):
        raise ValueError(f'Docling document absent from manifest: {sorted(extra)}')
    index = {}
    for key, (name, url) in manifest.items():
        doc = documents[key]
        pictures = {page for picture in doc.get('pictures', []) for page in _pages(picture)}
        headings = {}
        for item in doc.get('texts', []):
            text = item.get('text', '')
            if isinstance(text, str) and OUTLINE.search(text):
                for page in _pages(item):
                    headings.setdefault(page, text)
        if not (pages := pictures & headings.keys()):
            raise ValueError(f'no outline heading with same-page picture: {name}')
        page = min(pages)
        index[key] = {'source_url': url, 'outline_page': page, 'heading': headings[page]}
    return dict(sorted(index.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docling_dir', type=Path)
    parser.add_argument('manifest_path', type=Path)
    parser.add_argument('output_path', type=Path)
    args = parser.parse_args()
    index = build_outline_index(args.docling_dir, args.manifest_path)
    args.output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'manifest={len(read_manifest(args.manifest_path))} docling={len(list(args.docling_dir.glob("*.json")))} indexed={len(index)} exceptions=0')


if __name__ == '__main__':
    main()
