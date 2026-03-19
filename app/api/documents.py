"""文档上传与索引相关的路由实现（Step 2）。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.schemas.documents import DocumentDetail, DocumentListItem, DocumentUploadResponse
from app.services.inventory import InventoryService


router = APIRouter(prefix="/documents", tags=["documents"])
inventory_service = InventoryService(get_settings())


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> DocumentUploadResponse:
    document = await inventory_service.handle_upload(db, file)
    return DocumentUploadResponse.model_validate(document)


@router.get("", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentListItem]:
    documents = inventory_service.list_documents(db)
    return [DocumentListItem.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentDetail:
    document = inventory_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    document = inventory_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    inventory_service.delete_document(db, document)
    return {"status": "deleted"}
