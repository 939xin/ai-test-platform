"""
PDF 导出器 — 使用 Chrome Headless 将 HTML 报告转为 PDF
无需额外依赖，利用已有的 Selenium + Chrome
"""
import os
import base64
import tempfile
from app.utils.browser_manager import BrowserManager


def export_html_to_pdf(html_path: str, output_path: str = None) -> str:
    """
    将 HTML 报告导出为 PDF
    使用 Chrome Headless 的 CDP Page.printToPDF 功能

    Args:
        html_path: HTML 报告文件路径
        output_path: PDF 输出路径（可选，默认与 HTML 同目录同名 .pdf）

    Returns:
        PDF 文件路径，失败返回空字符串
    """
    if not output_path:
        output_path = os.path.splitext(html_path)[0] + '.pdf'

    driver = None
    try:
        driver = BrowserManager.create_driver("chrome", headless=True)
        # 使用 file:// 协议打开 HTML
        file_url = f"file:///{html_path.replace(chr(92), '/')}"
        driver.get(file_url)

        # 等待页面渲染
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # 使用 Chrome DevTools Protocol 生成 PDF
        pdf_params = {
            "landscape": False,
            "printBackground": True,
            "preferCSSPageSize": True,
            "paperWidth": 8.27,   # A4
            "paperHeight": 11.69,
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
        }

        result = driver.execute_cdp_cmd("Page.printToPDF", pdf_params)
        pdf_data = base64.b64decode(result['data'])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_data)

        return output_path

    except Exception as e:
        print(f"PDF 导出失败: {str(e)}")
        return ""
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
