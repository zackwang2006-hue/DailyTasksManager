import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.config import REPORTS_DIR
from app.models.plan import PlanLevel
from app.services.report_config import LLMConfig
from app.services.report_prompt_builder import ReportPromptBuilder


REPORT_DIR_NAMES = {
    PlanLevel.DAY.value: "daily",
    PlanLevel.WEEK.value: "weekly",
    PlanLevel.MONTH.value: "monthly",
    PlanLevel.QUARTER.value: "quarterly",
    PlanLevel.YEAR.value: "yearly",
    PlanLevel.FIVE_YEAR.value: "five_year",
}


class ReportGenerationService:
    def __init__(
        self,
        prompt_builder: ReportPromptBuilder | None = None,
        reports_dir: Path = REPORTS_DIR,
        sleep_func=time.sleep,
    ):
        self.prompt_builder = prompt_builder or ReportPromptBuilder()
        self.reports_dir = Path(reports_dir)
        self.sleep_func = sleep_func

    def generate_report(self, period_data: dict, llm_config: LLMConfig) -> tuple[str, str]:
        messages = self.prompt_builder.build_messages(period_data)
        payload = {
            "model": llm_config.model,
            "messages": messages,
            "temperature": llm_config.temperature,
        }
        url = f"{llm_config.base_url.rstrip('/')}/chat/completions"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {llm_config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=llm_config.timeout_seconds) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                markdown = self.extract_markdown(response_data)
                return self.prompt_builder.report_title(period_data), markdown
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as error:
                last_error = error
                if attempt < 2:
                    self.sleep_func(2 ** attempt)
        raise RuntimeError(f"报告生成失败：{last_error.__class__.__name__}")

    def test_connection(self, llm_config: LLMConfig) -> None:
        if not llm_config.api_key:
            raise ValueError("API Key 无效")
        if not llm_config.base_url:
            raise ValueError("Base URL 无法连接")
        if not llm_config.model:
            raise ValueError("模型不存在")

        payload = {
            "model": llm_config.model,
            "messages": [{"role": "user", "content": "回复 OK"}],
            "temperature": 0,
            "max_tokens": 1,
        }
        request = urllib.request.Request(
            f"{llm_config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {llm_config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=llm_config.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    raise RuntimeError("API 请求失败")
                json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise RuntimeError("API Key 无效") from error
            if error.code == 404:
                raise RuntimeError("模型不存在") from error
            raise RuntimeError("API 请求失败") from error
        except (TimeoutError, socket.timeout):
            raise RuntimeError("请求超时") from None
        except urllib.error.URLError:
            raise RuntimeError("网络连接失败") from None
        except json.JSONDecodeError:
            raise RuntimeError("API 返回内容无效") from None

    def extract_markdown(self, response_data: dict) -> str:
        choices = response_data.get("choices") or []
        if not choices:
            raise ValueError("API 返回内容为空")
        content = choices[0].get("message", {}).get("content", "")
        content = self.strip_outer_code_fence(str(content).strip())
        if not content:
            raise ValueError("API 返回报告为空")
        return content

    def strip_outer_code_fence(self, content: str) -> str:
        lines = content.splitlines()
        if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return content

    def save_report(self, period_data: dict, title: str, markdown: str) -> Path:
        period = period_data["period"]
        directory = self.reports_dir / REPORT_DIR_NAMES.get(period["type"], period["type"])
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.file_name(period_data, title)
        path.write_text(markdown, encoding="utf-8")
        return path

    def file_name(self, period_data: dict, title: str) -> str:
        period = period_data["period"]
        suffix = title.split(" ", 1)[-1] if " " in title else title
        safe_suffix = "".join(char for char in suffix if char not in '\\/:*?"<>|').strip() or "报告"
        if period["start"] == period["end"]:
            return f"{period['start']}_{safe_suffix}.md"
        return f"{period['start']}_{period['end']}_{safe_suffix}.md"
