from pydantic import BaseModel


class KnowledgeCategory(BaseModel):
    id: str
    name: str
    description: str
    parent_id: str | None = None
    doc_count: int = 0
    icon: str = ""
    color: str = ""


class KnowledgeItem(BaseModel):
    id: str
    title: str
    category_id: str
    category_name: str
    parent_category: str = ""
    knowledge_type: str
    source: str
    score: int = 5
    status: str = "已发布"
    update_time: str = ""
    file_path: str = ""
    description: str = ""


class KnowledgeStat(BaseModel):
    total_count: int = 0
    structured_count: int = 0
    unstructured_count: int = 0
    graph_entities: int = 0
    business_domains: int = 0
    completeness: float = 0.0
    availability: float = 0.0


class KnowledgeDetail(BaseModel):
    id: str
    title: str
    category_id: str
    category_name: str
    parent_category: str = ""
    knowledge_type: str
    source: str
    score: int = 5
    status: str = "已发布"
    update_time: str = ""
    file_path: str = ""
    description: str = ""
    content: str = ""
    tags: list[str] = []
