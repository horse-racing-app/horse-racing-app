from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ==========================================
# ★ ここにステップ2で取得したSupabaseのURLを貼り付けます
# 【注意】[YOUR-PASSWORD] の部分は、[ ]ごとご自身のパスワードに書き換えてください！
# ==========================================
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://postgres.zmfrluxczpxmdljlfhxx:.Ym6pDcH4&_uJ#5@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

# SQLite用のオプションを削除し、PostgreSQL用に変更
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Race(Base):
    __tablename__ = "races"
    id = Column(Integer, primary_key=True, index=True)
    netkeiba_id = Column(String, nullable=True)
    date = Column(String)
    course = Column(String)
    race_number = Column(Integer)
    name = Column(String)
    distance = Column(Integer)
    condition = Column(String)
    predictions_json = Column(String, nullable=True)
    result_json = Column(String, nullable=True)

    entries = relationship("RaceEntry", back_populates="race")

class RaceEntry(Base):
    __tablename__ = "race_entries"
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races.id"))
    horse_number = Column(Integer)
    horse_name = Column(String)
    jockey = Column(String)
    weight = Column(String)
    odds = Column(Float)
    sex_age = Column(String, default="不明")
    trainer = Column(String, default="不明")
    past_performance = Column(String, default="") 
    
    race = relationship("Race", back_populates="entries")

# Supabase上にテーブルを自動作成
Base.metadata.create_all(bind=engine)