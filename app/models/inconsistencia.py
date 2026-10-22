from app.extensions import db


class Inconsistencia(db.Model):
    __tablename__ = "inconsistencia"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(2), nullable=False)  # "R1" o "R2"
    muestra_id = db.Column(db.String, nullable=True)
    sondaje_id = db.Column(db.String, nullable=False)
    descripcion = db.Column(db.String, nullable=False)
