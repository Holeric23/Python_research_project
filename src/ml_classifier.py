import numpy as np
import pandas as pd
from typing import Dict, Tuple, Any, List
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

def create_single_pipeline(penalty: str, C: float) -> Pipeline:
    """
    Создает одиночный пайплайн TF-IDF + LogisticRegression с заданным штрафом.
    """
    penalty_param = None if penalty == "none" else penalty
    
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\b[а-яёa-z][а-яёa-z0-9_-]{2,}\b"
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",
            penalty=penalty_param,
            C=C,
            solver="saga",
            random_state=42,
            max_iter=1000
        ))
    ])

def build_binary_pipeline() -> Tuple[GridSearchCV, Pipeline]:
    """
    Создает GridSearchCV для подбора гиперпараметров.
    На основе научного анализа мы ищем оптимальные параметры строго в рамках L2 (Ridge) регуляризации.
    """
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\b[а-яёa-z][а-яёa-z0-9_-]{2,}\b"
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",
            solver="saga",
            random_state=42,
            max_iter=1000
        ))
    ])

    # Ищем лучшую модель строго среди L2-регуляризаций разной силы
    param_grid = {
        "clf__penalty": ["l2"],
        "clf__C": [0.1, 0.5, 1.0, 5.0, 10.0]
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    grid_search = GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        verbose=0
    )

    return grid_search, pipeline

def get_binary_oof_predictions(X: np.ndarray, y: np.ndarray, estimator: Pipeline) -> np.ndarray:
    """
    Вычисляет Out-of-Fold предсказания на кросс-валидации.
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    return cross_val_predict(estimator, X, y, cv=cv, n_jobs=-1)

def transform_prob_to_signed_score(prob_vacancy: np.ndarray) -> np.ndarray:
    """
    Масштабирует вероятность [0.0, 1.0] в симметричную шкалу [-1.0, +1.0].
    """
    return 2 * prob_vacancy - 1

def get_confidence_tier(score: float) -> str:
    """
    Группирует непрерывную шкалу в качественные градации.
    """
    if score >= 0.90:
        return "Ultra-Strict Vacancy"
    elif score >= 0.80:
        return "Strict Vacancy"
    elif score >= 0.60:
        return "Moderate Vacancy"
    elif score >= 0.50:
        return "Mild Vacancy"
    elif score <= -0.70:
        return "Resume"
    else:
        return "Trash / Uncertain"

def extract_binary_feature_importance(pipeline: Pipeline, top_n: int = 15) -> Dict[str, List[Tuple[str, float]]]:
    """
    Адаптивно извлекает веса признаков для Вакансий (стремятся к +1) 
    и Резюме (стремятся к -1) с защитой от вывода пустых или нулевых (алфавитных) признаков.
    """
    vectorizer = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["clf"]

    feature_names = np.array(vectorizer.get_feature_names_out())
    coef = classifier.coef_

    # Извлекаем одномерный массив весов
    weights = coef[0]
    sorted_idx = weights.argsort()

    # Извлекаем Вакансии (самые большие ПОЛОЖИТЕЛЬНЫЕ веса)
    # Фильтруем строго больше 0, чтобы избежать вывода "алфавитных нулей" L1-регуляризации
    vacancy_features = []
    for idx in sorted_idx[::-1]:
        w = float(weights[idx])
        if w > 0.0001:  # Берем только реальные положительные признаки
            vacancy_features.append((feature_names[idx], round(w, 4)))
        if len(vacancy_features) >= top_n:
            break

    # Извлекаем Резюме (самые большие по модулю ОТРИЦАТЕЛЬНЫЕ веса)
    # Фильтруем строго меньше 0
    resume_features = []
    for idx in sorted_idx:
        w = float(weights[idx])
        if w < -0.0001:  # Берем только реальные отрицательные признаки
            resume_features.append((feature_names[idx], round(w, 4)))
        if len(resume_features) >= top_n:
            break

    return {
        "Vacancy": vacancy_features,
        "Resume": resume_features
    }