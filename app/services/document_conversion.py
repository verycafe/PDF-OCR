"""
文档转换服务 - 将上传的 Office 文档转换为 PDF
依赖 LibreOffice 进行版式保真的 PDF 转换，适用于容器化部署和服务器环境。
"""
import glob
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from functools import lru_cache

SUPPORTED_DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'doc'}
OFFICE_DOCUMENT_EXTENSIONS = {'docx', 'doc'}
LIBREOFFICE_CANDIDATES = [
    os.environ.get('SOFFICE_PATH'),
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    '/usr/bin/soffice',
    '/usr/bin/libreoffice',
    shutil.which('soffice'),
    shutil.which('libreoffice'),
]


class DocumentConversionError(RuntimeError):
    """文档转换失败时抛出的异常"""


def get_file_extension(filename):
    """获取文件扩展名（不带点，统一小写）"""
    return os.path.splitext(filename or '')[1].lower().lstrip('.')


@lru_cache(maxsize=1)
def get_available_soffice():
    """定位当前机器上可用的 LibreOffice 二进制"""
    dynamic_candidates = glob.glob('/opt/homebrew/Caskroom/libreoffice/*/LibreOffice.app/Contents/MacOS/soffice')

    for candidate in [*LIBREOFFICE_CANDIDATES, *dynamic_candidates]:
        if not candidate:
            continue

        if not os.path.exists(candidate) or not os.access(candidate, os.X_OK):
            continue

        try:
            subprocess.run(
                [candidate, '--headless', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=15,
                text=True,
            )
            return candidate
        except (subprocess.SubprocessError, OSError):
            continue

    return None


def convert_office_document_to_pdf(source_path, target_pdf_path):
    """使用 LibreOffice 将 DOC/DOCX 转换为 PDF"""
    soffice = get_available_soffice()
    if not soffice:
        raise DocumentConversionError(
            'LibreOffice/soffice is required for DOC/DOCX conversion. '
            'Ensure the runtime image installs LibreOffice and exposes soffice on PATH.'
        )

    output_dir = os.path.dirname(target_pdf_path)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='libreoffice-profile-') as profile_dir:
        user_installation = Path(profile_dir).resolve().as_uri()

        try:
            completed = subprocess.run(
                [
                    soffice,
                    f'-env:UserInstallation={user_installation}',
                    '--headless',
                    '--nologo',
                    '--nodefault',
                    '--nolockcheck',
                    '--nofirststartwizard',
                    '--convert-to',
                    'pdf:writer_pdf_Export',
                    '--outdir',
                    output_dir,
                    source_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=180,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            command_output = '\n'.join(part for part in [exc.stdout, exc.stderr] if part).strip()
            raise DocumentConversionError(
                'LibreOffice conversion failed'
                + (f': {command_output}' if command_output else f': {exc}')
            ) from exc
        except OSError as exc:
            raise DocumentConversionError(f'LibreOffice conversion failed: {exc}') from exc

    generated_pdf_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(source_path))[0]}.pdf")

    if not os.path.exists(generated_pdf_path):
        command_output = '\n'.join(part for part in [completed.stdout, completed.stderr] if part).strip()
        raise DocumentConversionError(
            'LibreOffice conversion did not produce a PDF file'
            + (f': {command_output}' if command_output else '')
        )

    if generated_pdf_path != target_pdf_path:
        os.replace(generated_pdf_path, target_pdf_path)

    return target_pdf_path
