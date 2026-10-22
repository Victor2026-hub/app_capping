from app.extensions import db


class Muestra(db.Model):
    __tablename__ = "muestra"

    muestra_id = db.Column(db.String, primary_key=True)
    sondaje_id = db.Column(db.String, db.ForeignKey("sondaje.sondaje_id"), nullable=False)
    desde_m = db.Column(db.Float)
    hasta_m = db.Column(db.Float)
    au_original = db.Column(db.Float, nullable=False)
    au_gpt = db.Column(db.Float, nullable=False)
    lote = db.Column(db.String)

    sondaje = db.relationship("Sondaje", back_populates="muestras")
