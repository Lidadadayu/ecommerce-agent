from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from agent.evidence_store import (
    get_evidence,
    list_evidences,
    resolve_evidence_path,
    save_order_screenshot,
)


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/order-screenshot")
async def upload_order_screenshot(
    file: UploadFile = File(...),
    customer_id: str = Form(...),
    session_id: str | None = Form(default=None),
    order_id: str | None = Form(default=None),
    note: str | None = Form(default=None),
) -> dict[str, Any]:
    """
    上传订单截图凭证。

    当前只负责保存截图并生成 evidence_id，不做 OCR。
    业务含义：
    - 用户在申请售后前或售后过程中上传订单截图；
    - 前端把 evidence_id 写入 memory；
    - 后续创建售后工单或人工审核可引用该凭证。
    """

    try:
        content = await file.read()
        record = save_order_screenshot(
            content=content,
            filename=file.filename or "order_screenshot.png",
            customer_id=customer_id.strip(),
            session_id=(session_id or "").strip() or None,
            order_id=(order_id or "").strip() or None,
            content_type=file.content_type,
            note=note,
        )

        # 注意：这里不要同步调用视觉模型。
        # 视觉识别可能需要 10~30 秒甚至超时；如果放在上传接口里，
        # Streamlit 点击“发送”后会一直卡在上传阶段，用户会感觉按钮没反应。
        # 正确流程是：上传接口只保存凭证并快速返回 evidence_id；
        # 随后的 Agent 对话流再通过 screenshot_order_review 工具识别截图，
        # 这样前端可以显示“正在处理”的气泡和进度状态。

        return {
            "success": True,
            "message": "订单截图上传成功，已关联当前对话。",
            "evidence": record,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传失败：{type(exc).__name__}: {exc}") from exc


@router.get("/evidences")
def query_evidences(
    customer_id: str | None = None,
    session_id: str | None = None,
    order_id: str | None = None,
    evidence_type: str | None = "order_screenshot",
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    evidences = list_evidences(
        customer_id=customer_id,
        session_id=session_id,
        order_id=order_id,
        evidence_type=evidence_type,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(evidences),
        "evidences": evidences,
    }


@router.get("/evidences/{evidence_id}")
def read_evidence(evidence_id: str) -> dict[str, Any]:
    evidence = get_evidence(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"未找到凭证：{evidence_id}")

    return {
        "success": True,
        "evidence": evidence,
    }


@router.get("/files/{evidence_id}")
def read_evidence_file(evidence_id: str) -> FileResponse:
    evidence = get_evidence(evidence_id)
    path = resolve_evidence_path(evidence_id)

    if not evidence or not path:
        raise HTTPException(status_code=404, detail=f"未找到凭证文件：{evidence_id}")

    return FileResponse(
        path=path,
        media_type=evidence.get("content_type") or "application/octet-stream",
        filename=evidence.get("original_filename") or path.name,
    )
