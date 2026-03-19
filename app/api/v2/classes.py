"""班级邀请码与入班管理 API。"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v2.auth import get_current_user, require_student, require_teacher
from app.contracts.classroom import (
    ClassGroupAssignRequest,
    ClassGroupCreate,
    ClassGroupDetailResponse,
    ClassGroupListResponse,
    ClassGroupMemberResponse,
    ClassGroupResponse,
    ClassroomCreate,
    ClassroomListResponse,
    ClassroomMemberListResponse,
    ClassroomMemberResponse,
    ClassroomResponse,
    JoinClassRequest,
    JoinClassResponse,
)
from app.db import get_db
from app.models import (
    ClassGroup,
    ClassGroupMember,
    ClassMember,
    Classroom,
    User,
    UserRole,
)

router = APIRouter()


def _generate_invite_code(db: Session, length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = db.query(Classroom).filter(Classroom.invite_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="邀请码生成失败，请稍后重试")


def _member_count(db: Session, classroom_id: int) -> int:
    return db.query(ClassMember).filter(ClassMember.classroom_id == classroom_id).count()


def _group_member_count(db: Session, group_id: int) -> int:
    return db.query(ClassGroupMember).filter(ClassGroupMember.group_id == group_id).count()


def _to_classroom_response(
    db: Session,
    classroom: Classroom,
    include_teacher: bool = False,
    joined_group: Optional[Tuple[int, str]] = None,
) -> ClassroomResponse:
    teacher_name = None
    if include_teacher:
        teacher = db.query(User).filter(User.id == classroom.teacher_id).first()
        teacher_name = teacher.name if teacher else None

    joined_group_id: Optional[int] = None
    joined_group_name: Optional[str] = None
    if joined_group:
        joined_group_id, joined_group_name = joined_group

    return ClassroomResponse(
        id=classroom.id,
        name=classroom.name,
        grade=classroom.grade,
        invite_code=classroom.invite_code,
        teacher_id=classroom.teacher_id,
        teacher_name=teacher_name,
        member_count=_member_count(db, classroom.id),
        joined_group_id=joined_group_id,
        joined_group_name=joined_group_name,
        created_at=classroom.created_at,
        updated_at=classroom.updated_at,
    )


def _to_class_group_response(db: Session, group: ClassGroup) -> ClassGroupResponse:
    return ClassGroupResponse(
        id=group.id,
        classroom_id=group.classroom_id,
        name=group.name,
        member_count=_group_member_count(db, group.id),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _build_group_name_map(db: Session, classroom_id: int) -> Dict[int, str]:
    groups = db.query(ClassGroup).filter(ClassGroup.classroom_id == classroom_id).all()
    return {group.id: group.name for group in groups}


def _to_class_group_detail_response(
    db: Session,
    group: ClassGroup,
) -> ClassGroupDetailResponse:
    members = (
        db.query(ClassGroupMember)
        .filter(ClassGroupMember.group_id == group.id)
        .order_by(ClassGroupMember.assigned_at.asc())
        .all()
    )

    member_items: List[ClassGroupMemberResponse] = []
    for item in members:
        student = db.query(User).filter(User.id == item.student_id).first()
        if not student:
            continue
        member_items.append(
            ClassGroupMemberResponse(
                id=item.id,
                classroom_id=item.classroom_id,
                group_id=item.group_id,
                student_id=student.id,
                student_name=student.name,
                student_username=student.username,
                student_grade=student.grade,
                student_class_name=student.class_name,
                assigned_at=item.assigned_at,
            )
        )

    return ClassGroupDetailResponse(
        id=group.id,
        classroom_id=group.classroom_id,
        name=group.name,
        member_count=len(member_items),
        members=member_items,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _get_teacher_classroom(db: Session, class_id: int, teacher_id: int) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="班级不存在")
    if classroom.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="只能管理自己创建的班级")
    return classroom


def _get_teacher_group(db: Session, class_id: int, group_id: int, teacher_id: int) -> ClassGroup:
    _get_teacher_classroom(db, class_id, teacher_id)
    group = (
        db.query(ClassGroup)
        .filter(ClassGroup.id == group_id, ClassGroup.classroom_id == class_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="小组不存在")
    return group


@router.post("/", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
async def create_classroom(
    data: ClassroomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="班级名称不能为空")

    duplicate = (
        db.query(Classroom)
        .filter(
            Classroom.teacher_id == current_user.id,
            Classroom.name == name,
            Classroom.grade == data.grade,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该班级已存在")

    classroom = Classroom(
        name=name,
        grade=data.grade,
        invite_code=_generate_invite_code(db),
        teacher_id=current_user.id,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return _to_classroom_response(db, classroom)


@router.get("/my", response_model=ClassroomListResponse)
async def list_my_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.TEACHER:
        classes = (
            db.query(Classroom)
            .filter(Classroom.teacher_id == current_user.id)
            .order_by(Classroom.created_at.desc())
            .all()
        )
        items = [_to_classroom_response(db, classroom) for classroom in classes]
        return {"classes": items, "total": len(items)}

    memberships = (
        db.query(ClassMember)
        .filter(ClassMember.student_id == current_user.id)
        .order_by(ClassMember.joined_at.desc())
        .all()
    )
    class_ids = [member.classroom_id for member in memberships]
    if not class_ids:
        return {"classes": [], "total": 0}

    classrooms = (
        db.query(Classroom)
        .filter(Classroom.id.in_(class_ids))
        .all()
    )
    classroom_by_id = {classroom.id: classroom for classroom in classrooms}

    group_links = (
        db.query(ClassGroupMember)
        .filter(
            ClassGroupMember.student_id == current_user.id,
            ClassGroupMember.classroom_id.in_(class_ids),
        )
        .all()
    )
    class_to_group_id = {item.classroom_id: item.group_id for item in group_links}
    group_ids = [item.group_id for item in group_links]

    group_name_by_id: Dict[int, str] = {}
    if group_ids:
        groups = db.query(ClassGroup).filter(ClassGroup.id.in_(group_ids)).all()
        group_name_by_id = {group.id: group.name for group in groups}

    items: List[ClassroomResponse] = []
    for member in memberships:
        classroom = classroom_by_id.get(member.classroom_id)
        if not classroom:
            continue
        joined_group = None
        group_id = class_to_group_id.get(classroom.id)
        if group_id is not None:
            joined_group = (group_id, group_name_by_id.get(group_id, "未命名小组"))
        items.append(
            _to_classroom_response(
                db,
                classroom,
                include_teacher=True,
                joined_group=joined_group,
            )
        )

    return {"classes": items, "total": len(items)}


@router.post("/join", response_model=JoinClassResponse)
async def join_classroom(
    data: JoinClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    invite_code = data.invite_code.strip().upper()
    classroom = db.query(Classroom).filter(Classroom.invite_code == invite_code).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="邀请码无效，请检查后重试")

    if current_user.grade is not None and current_user.grade != classroom.grade:
        raise HTTPException(
            status_code=400,
            detail="邀请码对应班级年级与当前学生账号年级不一致",
        )

    existing_member = (
        db.query(ClassMember)
        .filter(
            ClassMember.classroom_id == classroom.id,
            ClassMember.student_id == current_user.id,
        )
        .first()
    )

    if existing_member:
        return JoinClassResponse(
            classroom=_to_classroom_response(db, classroom, include_teacher=True),
            joined=False,
            message="你已在该班级中",
        )

    member = ClassMember(classroom_id=classroom.id, student_id=current_user.id)
    db.add(member)
    current_user.class_name = classroom.name
    if current_user.grade is None:
        current_user.grade = classroom.grade
    db.commit()

    return JoinClassResponse(
        classroom=_to_classroom_response(db, classroom, include_teacher=True),
        joined=True,
        message="入班成功",
    )


@router.get("/{class_id}/members", response_model=ClassroomMemberListResponse)
async def list_class_members(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    classroom = _get_teacher_classroom(db, class_id, current_user.id)

    members = (
        db.query(ClassMember)
        .filter(ClassMember.classroom_id == class_id)
        .order_by(ClassMember.joined_at.asc())
        .all()
    )

    group_name_by_id = _build_group_name_map(db, class_id)
    group_members = (
        db.query(ClassGroupMember)
        .filter(ClassGroupMember.classroom_id == class_id)
        .all()
    )
    student_group_map: Dict[int, Tuple[int, Optional[str]]] = {
        item.student_id: (item.group_id, group_name_by_id.get(item.group_id))
        for item in group_members
    }

    items: List[ClassroomMemberResponse] = []
    for member in members:
        student = db.query(User).filter(User.id == member.student_id).first()
        if not student:
            continue
        group_info = student_group_map.get(student.id)
        group_id = group_info[0] if group_info else None
        group_name = group_info[1] if group_info else None
        items.append(
            ClassroomMemberResponse(
                member_id=member.id,
                student_id=student.id,
                student_name=student.name,
                student_username=student.username,
                student_grade=student.grade,
                student_class_name=student.class_name,
                group_id=group_id,
                group_name=group_name,
                joined_at=member.joined_at,
            )
        )

    return {
        "classroom": _to_classroom_response(db, classroom),
        "members": items,
        "total": len(items),
    }


@router.get("/{class_id}/groups", response_model=ClassGroupListResponse)
async def list_class_groups(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    classroom = _get_teacher_classroom(db, class_id, current_user.id)
    groups = (
        db.query(ClassGroup)
        .filter(ClassGroup.classroom_id == class_id)
        .order_by(ClassGroup.created_at.asc())
        .all()
    )
    items = [_to_class_group_detail_response(db, group) for group in groups]
    return {
        "classroom": _to_classroom_response(db, classroom),
        "groups": items,
        "total": len(items),
    }


@router.post("/{class_id}/groups", response_model=ClassGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_class_group(
    class_id: int,
    data: ClassGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    _get_teacher_classroom(db, class_id, current_user.id)
    group_name = data.name.strip()
    if not group_name:
        raise HTTPException(status_code=400, detail="小组名称不能为空")

    duplicate = (
        db.query(ClassGroup)
        .filter(
            ClassGroup.classroom_id == class_id,
            ClassGroup.name == group_name,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该班级内小组名称已存在")

    group = ClassGroup(classroom_id=class_id, name=group_name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _to_class_group_response(db, group)


@router.post("/{class_id}/groups/{group_id}/members", response_model=ClassGroupDetailResponse)
async def assign_class_group_member(
    class_id: int,
    group_id: int,
    data: ClassGroupAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    group = _get_teacher_group(db, class_id, group_id, current_user.id)
    member = (
        db.query(ClassMember)
        .filter(
            ClassMember.classroom_id == class_id,
            ClassMember.student_id == data.student_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=400, detail="该学生尚未加入班级")

    group_member = (
        db.query(ClassGroupMember)
        .filter(
            ClassGroupMember.classroom_id == class_id,
            ClassGroupMember.student_id == data.student_id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if group_member:
        group_member.group_id = group.id
        group_member.assigned_at = now
    else:
        db.add(
            ClassGroupMember(
                classroom_id=class_id,
                group_id=group.id,
                student_id=data.student_id,
                assigned_at=now,
            )
        )

    db.commit()
    db.refresh(group)
    return _to_class_group_detail_response(db, group)


@router.delete("/{class_id}/groups/{group_id}/members/{student_id}", response_model=ClassGroupDetailResponse)
async def remove_class_group_member(
    class_id: int,
    group_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    group = _get_teacher_group(db, class_id, group_id, current_user.id)
    group_member = (
        db.query(ClassGroupMember)
        .filter(
            ClassGroupMember.classroom_id == class_id,
            ClassGroupMember.group_id == group_id,
            ClassGroupMember.student_id == student_id,
        )
        .first()
    )
    if not group_member:
        raise HTTPException(status_code=404, detail="该学生不在此小组中")

    db.delete(group_member)
    db.commit()
    db.refresh(group)
    return _to_class_group_detail_response(db, group)


@router.delete("/{class_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class_group(
    class_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    group = _get_teacher_group(db, class_id, group_id, current_user.id)
    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{class_id}/invite-code/reset", response_model=ClassroomResponse)
async def reset_invite_code(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    classroom = _get_teacher_classroom(db, class_id, current_user.id)
    classroom.invite_code = _generate_invite_code(db)
    db.commit()
    db.refresh(classroom)
    return _to_classroom_response(db, classroom)
