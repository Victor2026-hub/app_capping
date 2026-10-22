from app.extensions import db


class Sondaje(db.Model):
    __tablename__ = "sondaje"

    sondaje_id = db.Column(db.String, primary_key=True)
    zona = db.Column(db.String, nullable=False)
    este_m = db.Column(db.Float)
    norte_m = db.Column(db.Float)
    elevacion_m = db.Column(db.Float)
    azimut = db.Column(db.Float)
    buzamiento = db.Column(db.Float)
    profundidad_m = db.Column(db.Float)

    muestras = db.relationship("Muestra", back_populates="sondaje")
