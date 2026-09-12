import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Pump, Tannery
from app.models.auth import User
from app.security import require_roles

router = APIRouter(prefix='/api/pumps', tags=['pumps'],
                   dependencies=[Depends(require_roles('talco_admin', 'talco_staff'))])


class PumpInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    code: str = Field(min_length=1, max_length=20, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    name: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator('code')
    @classmethod
    def uppercase_code(cls, value: str) -> str:
        return value.upper()


class PumpOut(PumpInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tannery_count: int = 0


def output(session: Session, pump: Pump) -> dict:
    values = PumpOut.model_validate(pump).model_dump()
    values['tannery_count'] = session.scalar(select(func.count()).select_from(Tannery).where(Tannery.pump_house == pump.code))
    return values


def find(session: Session, pump_id: int) -> Pump:
    pump = session.get(Pump, pump_id)
    if pump is None:
        raise HTTPException(404, 'Pump not found')
    return pump


def save(session: Session, pump: Pump, actor: User, action: str, changes: dict):
    try:
        session.flush()
        session.add(AuditLog(entity_type='pump', entity_id=pump.id, action=action,
                             changed_by=actor.email, changes=json.dumps(changes)))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Pump code already exists or this pump is linked to a tannery') from exc


@router.get('', response_model=list[PumpOut])
def list_pumps(session: Session = Depends(get_db)):
    return [output(session, pump) for pump in session.scalars(select(Pump).order_by(Pump.code))]


@router.get('/{pump_id}', response_model=PumpOut)
def get_pump(pump_id: int, session: Session = Depends(get_db)):
    return output(session, find(session, pump_id))


@router.post('', response_model=PumpOut, status_code=201)
def create_pump(data: PumpInput, session: Session = Depends(get_db),
                actor: User = Depends(require_roles('talco_admin'))):
    pump = Pump(**data.model_dump())
    session.add(pump)
    save(session, pump, actor, 'create', data.model_dump())
    return output(session, pump)


@router.patch('/{pump_id}', response_model=PumpOut)
def update_pump(pump_id: int, data: PumpInput, session: Session = Depends(get_db),
                actor: User = Depends(require_roles('talco_admin'))):
    pump = find(session, pump_id)
    changes = {}
    for key, value in data.model_dump().items():
        old = getattr(pump, key)
        if old != value:
            changes[key] = {'from': old, 'to': value}
            setattr(pump, key, value)
    if changes:
        # The foreign key cascades code changes to all assigned tanneries.
        save(session, pump, actor, 'update', changes)
    return output(session, pump)


@router.delete('/{pump_id}', status_code=204)
def delete_pump(pump_id: int, session: Session = Depends(get_db),
                actor: User = Depends(require_roles('talco_admin'))):
    pump = find(session, pump_id)
    if session.scalar(select(Tannery.id).where(Tannery.pump_house == pump.code).limit(1)) is not None:
        raise HTTPException(409, 'Cannot delete: reassign the tanneries linked to this pump first')
    snapshot = PumpOut.model_validate(pump).model_dump()
    session.delete(pump)
    save(session, pump, actor, 'delete', snapshot)
