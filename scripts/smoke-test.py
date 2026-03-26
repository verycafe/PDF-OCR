#!/usr/bin/env python3
"""
Docker 部署冒烟测试

覆盖链路：
1. 健康检查与首页访问
2. 容器内 OCR / PPStructure 依赖验收
3. 创建项目
4. 上传 PDF / DOCX / DOC
5. 轮询等待处理完成
6. 验证 PDF 预览与 Markdown 下载
7. 验证项目批量下载 ZIP
8. 验证项目正常删除
9. 验证“处理中项目”的二次删除语义（409 -> force 删除）
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    log(f"+ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="", flush=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="", flush=True)
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result


def http_request(
    base_url: str,
    method: str,
    path: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, bytes, dict[str, str]]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers.items())


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, dict | list | str | None, dict[str, str]]:
    status, body, response_headers = http_request(
        base_url,
        method,
        path,
        data=data,
        headers=headers,
        timeout=timeout,
    )
    if not body:
        return status, None, response_headers

    try:
        return status, json.loads(body.decode("utf-8")), response_headers
    except json.JSONDecodeError:
        return status, body.decode("utf-8", errors="replace"), response_headers


def ensure_status(actual: int, expected: int, message: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{message}: expected {expected}, got {actual}")


def wait_for_service(base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, payload, _ = request_json(base_url, "GET", "/api/health", timeout=10)
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                log("Service health check passed.")
                return
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(2)
    if last_error is not None:
        raise RuntimeError(f"Timed out waiting for /api/health to become ready: {last_error}")
    raise RuntimeError("Timed out waiting for /api/health to become ready")


def build_multipart_body(file_path: Path) -> tuple[bytes, str]:
    boundary = f"codex-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8"),
        file_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def upload_document(base_url: str, project_id: int, file_path: Path) -> dict:
    payload, boundary = build_multipart_body(file_path)
    status, response_json, _ = request_json(
        base_url,
        "POST",
        f"/api/documents/upload/{project_id}",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=120,
    )
    ensure_status(status, 201, f"Upload failed for {file_path.name}")
    if not isinstance(response_json, list) or not response_json:
        raise RuntimeError(f"Unexpected upload response for {file_path.name}: {response_json}")
    log(f"Uploaded {file_path.name} as document {response_json[0]['id']}")
    return response_json[0]


def wait_for_documents(base_url: str, project_id: int, doc_ids: set[int], timeout_seconds: int) -> dict[int, dict]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status, payload, _ = request_json(base_url, "GET", f"/api/documents/project/{project_id}", timeout=20)
        ensure_status(status, 200, "Failed to fetch project documents")
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected document list response: {payload}")

        docs = {doc["id"]: doc for doc in payload if doc.get("id") in doc_ids}
        if doc_ids.issubset(docs.keys()):
            failed = [doc for doc in docs.values() if doc.get("status") in {"failed", "cancelled"}]
            if failed:
                raise RuntimeError(f"Document processing failed: {failed}")

            if all(doc.get("status") == "completed" for doc in docs.values()):
                log("All uploaded documents completed processing.")
                return docs

        time.sleep(2)

    raise RuntimeError("Timed out waiting for uploaded documents to complete")


def verify_document_outputs(base_url: str, doc: dict) -> None:
    doc_id = doc["id"]

    preview_status, _, preview_headers = http_request(base_url, "GET", f"/api/documents/{doc_id}/file", timeout=30)
    ensure_status(preview_status, 200, f"Preview download failed for document {doc_id}")
    preview_type = preview_headers.get("Content-Type", "")
    if "application/pdf" not in preview_type:
        raise RuntimeError(f"Unexpected preview content type for document {doc_id}: {preview_type}")

    markdown_status, markdown_body, markdown_headers = http_request(
        base_url,
        "GET",
        f"/api/documents/{doc_id}/markdown",
        timeout=30,
    )
    ensure_status(markdown_status, 200, f"Markdown download failed for document {doc_id}")
    if len(markdown_body.strip()) == 0:
        raise RuntimeError(f"Empty markdown download for document {doc_id}")
    markdown_type = markdown_headers.get("Content-Type", "")
    if "text/markdown" not in markdown_type:
        raise RuntimeError(f"Unexpected markdown content type for document {doc_id}: {markdown_type}")


def verify_project_archive(base_url: str, project_id: int, expected_count: int) -> None:
    status, body, headers = http_request(base_url, "GET", f"/api/projects/{project_id}/markdown-archive", timeout=60)
    ensure_status(status, 200, "Project markdown archive download failed")
    archive_type = headers.get("Content-Type", "")
    if "application/zip" not in archive_type:
        raise RuntimeError(f"Unexpected archive content type: {archive_type}")

    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        markdown_files = [name for name in archive.namelist() if name.endswith(".md")]
        if len(markdown_files) != expected_count:
            raise RuntimeError(f"Expected {expected_count} markdown files in archive, found {len(markdown_files)}")


def create_project(base_url: str, name: str, description: str) -> dict:
    payload = json.dumps({"name": name, "description": description}).encode("utf-8")
    status, response_json, _ = request_json(
        base_url,
        "POST",
        "/api/projects/",
        data=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    ensure_status(status, 201, "Project creation failed")
    if not isinstance(response_json, dict):
        raise RuntimeError(f"Unexpected project creation response: {response_json}")
    log(f"Created project {response_json['id']} ({name})")
    return response_json


def delete_project(base_url: str, project_id: int, *, force: bool = False, expected_status: int = 200) -> dict | str | None:
    suffix = "?force=true" if force else ""
    status, response_json, _ = request_json(
        base_url,
        "DELETE",
        f"/api/projects/{project_id}{suffix}",
        timeout=30,
    )
    ensure_status(status, expected_status, f"Project delete request failed for {project_id}")
    return response_json


def verify_project_deleted(base_url: str, project_id: int) -> None:
    status, response_json, _ = request_json(base_url, "GET", f"/api/projects/{project_id}", timeout=30)
    ensure_status(status, 404, f"Deleted project {project_id} still exists")
    if not isinstance(response_json, dict) or response_json.get("error") not in {"项目不存在", "Project not found"}:
        raise RuntimeError(f"Unexpected deleted project lookup response: {response_json}")


def generate_fixtures(temp_dir: Path, image_name: str) -> dict[str, Path]:
    generator_script = """
import subprocess
from pathlib import Path

out_dir = Path("/fixtures")
html_path = out_dir / "smoke.html"

html_path.write_text(
    '''<!DOCTYPE html>
<html>
  <body>
    <h1>Smoke Test Document</h1>
    <p>This document exercises PDF, DOCX and DOC conversion.</p>
    <table border="1" cellspacing="0" cellpadding="4">
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Type</td><td>Smoke</td></tr>
      <tr><td>Format</td><td>OCR</td></tr>
    </table>
  </body>
</html>
''',
    encoding="utf-8",
)

subprocess.run(
    ["soffice", "--headless", "--convert-to", "docx:Office Open XML Text", "--outdir", str(out_dir), str(html_path)],
    check=True,
)
docx_path = out_dir / "smoke.docx"
subprocess.run(
    ["soffice", "--headless", "--convert-to", "doc:MS Word 97", "--outdir", str(out_dir), str(docx_path)],
    check=True,
)
subprocess.run(
    ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
    check=True,
)
"""

    run([
        "docker",
        "run",
        "--rm",
        "-v",
        f"{temp_dir}:/fixtures",
        image_name,
        "python",
        "-c",
        generator_script,
    ])

    fixtures = {
        "pdf": temp_dir / "smoke.pdf",
        "docx": temp_dir / "smoke.docx",
        "doc": temp_dir / "smoke.doc",
    }
    for label, path in fixtures.items():
        if not path.exists():
            raise RuntimeError(f"Fixture generation failed: missing {label} file at {path}")
    log(f"Generated fixtures in {temp_dir}")
    return fixtures


def verify_runtime_dependencies(app_service: str) -> None:
    ocr_script = (
        "from paddleocr import PaddleOCR;"
        "PaddleOCR(lang='ch', use_textline_orientation=False);"
        "print('ocr ok')"
    )
    deps_script = (
        "from paddlex.utils.deps import require_extra;"
        "require_extra('ocr', obj_name='PP-StructureV3');"
        "print('structure deps ok')"
    )

    run(["docker", "compose", "exec", "-T", app_service, "python", "-c", ocr_script])
    run(["docker", "compose", "exec", "-T", app_service, "python", "-c", deps_script])


def seed_busy_document(project_id: int, app_service: str) -> None:
    seeder_script = r"""
import os
from pathlib import Path
from app.models.document import Document
from app.models.project import Project
from config import Config

project_id = int(os.environ["PROJECT_ID"])
project = Project.get_by_id(project_id)
project_dir = Path(Config.UPLOAD_FOLDER) / str(project_id)
project_dir.mkdir(parents=True, exist_ok=True)
doc_path = project_dir / "busy.pdf"
doc_path.write_bytes(b"%PDF-1.4\n% busy smoke fixture\n")
Document.create(project=project, filename="busy.pdf", file_path=str(doc_path), status="queued")
"""

    run([
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"PROJECT_ID={project_id}",
        app_service,
        "python",
        "-c",
        seeder_script,
    ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PDF-OCR Docker smoke test")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", f"http://127.0.0.1:{os.environ.get('PORT', '5001')}"))
    parser.add_argument("--image-name", default=os.environ.get("IMAGE_NAME", "pdf-ocr-app"))
    parser.add_argument("--app-service", default=os.environ.get("APP_SERVICE", "app"))
    parser.add_argument("--service-timeout", type=int, default=int(os.environ.get("SMOKE_SERVICE_TIMEOUT_SEC", "120")))
    parser.add_argument("--processing-timeout", type=int, default=int(os.environ.get("SMOKE_PROCESSING_TIMEOUT_SEC", "1200")))
    parser.add_argument("--skip-health-check", action="store_true")
    parser.add_argument("--skip-runtime-deps", action="store_true")
    parser.add_argument("--only-health-check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    created_projects: list[int] = []

    if args.only_health_check and args.skip_health_check:
        raise RuntimeError("Cannot combine --only-health-check with --skip-health-check")

    if not args.skip_health_check:
        wait_for_service(args.base_url, args.service_timeout)
        root_status, _, _ = http_request(args.base_url, "GET", "/", timeout=30)
        ensure_status(root_status, 200, "Frontend index request failed")
        log("Frontend index check passed.")
    if args.only_health_check:
        log("Health-only smoke check passed.")
        return 0

    if not args.skip_runtime_deps:
        verify_runtime_dependencies(args.app_service)

    with tempfile.TemporaryDirectory(prefix="pdf-ocr-smoke-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        fixtures = generate_fixtures(temp_dir, args.image_name)

        try:
            project = create_project(args.base_url, "codex-smoke-project", "docker smoke test")
            created_projects.append(project["id"])

            uploaded_docs = []
            for key in ("pdf", "docx", "doc"):
                uploaded_docs.append(upload_document(args.base_url, project["id"], fixtures[key]))

            doc_ids = {doc["id"] for doc in uploaded_docs}
            docs = wait_for_documents(args.base_url, project["id"], doc_ids, args.processing_timeout)

            for doc_id in doc_ids:
                verify_document_outputs(args.base_url, docs[doc_id])

            verify_project_archive(args.base_url, project["id"], expected_count=3)
            delete_project(args.base_url, project["id"], expected_status=200)
            verify_project_deleted(args.base_url, project["id"])
            created_projects.remove(project["id"])

            busy_project = create_project(args.base_url, "codex-force-delete-project", "force delete smoke test")
            created_projects.append(busy_project["id"])
            seed_busy_document(busy_project["id"], args.app_service)

            first_delete = delete_project(args.base_url, busy_project["id"], expected_status=409)
            if not isinstance(first_delete, dict) or first_delete.get("code") != "project_has_active_documents":
                raise RuntimeError(f"Unexpected first force-delete response: {first_delete}")

            delete_project(args.base_url, busy_project["id"], force=True, expected_status=200)
            verify_project_deleted(args.base_url, busy_project["id"])
            created_projects.remove(busy_project["id"])

            log("Smoke test passed.")
            return 0
        finally:
            for project_id in list(created_projects):
                try:
                    delete_project(args.base_url, project_id, force=True, expected_status=200)
                except Exception as cleanup_error:
                    print(
                        f"Cleanup failed for project {project_id}: {cleanup_error}",
                        file=sys.stderr,
                        flush=True,
                    )


if __name__ == "__main__":
    raise SystemExit(main())
