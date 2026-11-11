"""GitHub Actions のワークフロー（.github/workflows/pages.yml）の構成のテスト．

ブラウザテストを Playwright 公式イメージのコンテナ内で行い，実行時に apt へ接続しないこと，
イメージの版と requirements_tools.txt の playwright の版が一致すること，
ブラウザテストを省略・無視してデプロイしないことを検査する．YAML の解析器を追加しないため，文字列で検査する．
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "requirements_tools.txt").read_text(encoding="utf-8")


def pinned_version(package):
    """requirements_tools.txt で固定した版を返す．

    Args:
        package (str): パッケージ名．
    Returns:
        str | None: 版（例: "1.49.1"）．無ければ None．
    """
    m = re.search(rf"^{re.escape(package)}==([0-9][0-9.]*)\s*$", REQUIREMENTS, re.M)
    return m.group(1) if m else None


def run_commands():
    """ワークフローの各行（空行とコメント行を除く）を返す．

    Returns:
        list[str]: 前後の空白を除いた行．
    """
    lines = [line.strip() for line in WORKFLOW.splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def test_container_image_matches_pinned_playwright():
    """コンテナのイメージが Playwright 公式イメージで，版が requirements_tools.txt と一致する．"""
    m = re.search(r"image:\s*mcr\.microsoft\.com/playwright/python:v([0-9.]+)-noble\b", WORKFLOW)
    assert m, "build ジョブが Playwright 公式イメージ（python，noble）を用いていない"
    assert m.group(1) == pinned_version("playwright")


def test_no_apt_at_runtime():
    """ブラウザの依存パッケージを実行時に apt で入れない（--with-deps，install-deps，apt-get を用いない）．"""
    text = "\n".join(run_commands())
    for word in ("--with-deps", "install-deps", "apt-get", "apt "):
        assert word not in text, word


def test_browser_tests_are_not_skipped():
    """pytest で tests/ 全体を実行し，失敗を無視する設定が無い．"""
    assert re.search(r"run:\s*python -m pytest -q tests\s*$", WORKFLOW, re.M)
    assert "continue-on-error" not in WORKFLOW
    assert "--ignore" not in WORKFLOW and "-k " not in WORKFLOW


def test_deploy_requires_build():
    """デプロイはテストを含む build ジョブの成功後に限る．"""
    deploy = WORKFLOW.split("\n  deploy:", 1)[1]
    assert re.search(r"needs:\s*build\b", deploy)
    build = WORKFLOW.split("\n  build:", 1)[1].split("\n  deploy:", 1)[0]
    assert build.index("python -m pytest") < build.index("upload-pages-artifact")
