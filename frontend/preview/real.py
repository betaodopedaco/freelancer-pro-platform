"""
makita/preview/real.py
=======================
Busca sinais REAIS do banco de dados para o Momento Aha.

Uso:
    from makita.preview.real import buscar_sinais_reais
    
    sinais = buscar_sinais_reais(nicho="saas", quantidade=4)
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

try:
    from logger import get_logger
    log = get_logger("preview.real")
except ImportError:
    import logging
    log = logging.getLogger("preview.real")
    log.setLevel(logging.INFO)


def buscar_sinais_reais(
    nicho: str,
    quantidade: int = 4,
    plataformas: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Busca sinais reais do banco de dados para um nicho específico.
    
    Args:
        nicho: ID do nicho (ex: "saas", "imobiliario")
        quantidade: Quantidade de sinais a retornar (padrão: 4)
        plataformas: Lista de plataformas para filtrar (opcional)
    
    Returns:
        Lista de sinais reais do banco
    """
    try:
        # Tentar importar o banco de dados
        from makita.comum.db import get_db
        from makita.comum.modelos import Sinal
        
        db = get_db()
        
        # Buscar sinais do nicho
        query = db.query(Sinal).filter(
            Sinal.nicho == nicho,
            Sinal.relevancia >= 0.7  # Apenas sinais relevantes
        ).order_by(
            Sinal.timestamp.desc()
        ).limit(quantidade)
        
        # Filtrar por plataformas se fornecido
        if plataformas:
            query = query.filter(Sinal.plataforma.in_(plataformas))
        
        sinais = query.all()
        
        # Converter para dict
        resultado = []
        for sinal in sinais:
            resultado.append({
                "id": sinal.id,
                "plataforma": sinal.plataforma,
                "tipo": sinal.tipo,
                "titulo": sinal.titulo,
                "descricao": sinal.descricao,
                "autor": sinal.autor,
                "relevancia": sinal.relevancia,
                "timestamp": sinal.timestamp.isoformat() if sinal.timestamp else datetime.now().isoformat(),
                "link": sinal.link,
                "nicho": sinal.nicho,
            })
        
        log.info(f"Encontrados {len(resultado)} sinais reais para nicho '{nicho}'")
        
        return resultado
    
    except Exception as e:
        log.error(f"Erro ao buscar sinais reais: {e}")
        # Fallback para mockados se houver erro
        from makita.preview.gerador import gerar_sinais_mock
        return gerar_sinais_mock(nicho=nicho, quantidade=quantidade, plataformas=plataformas)


def buscar_estatisticas_reais(nicho: str) -> Dict[str, Any]:
    """
    Busca estatísticas reais do banco de dados.
    
    Args:
        nicho: ID do nicho
    
    Returns:
        Dict com estatísticas reais
    """
    try:
        from makita.comum.db import get_db
        from makita.comum.modelos import Sinal
        from sqlalchemy import func
        
        db = get_db()
        
        # Total de sinais do nicho
        total = db.query(func.count(Sinal.id)).filter(
            Sinal.nicho == nicho
        ).scalar() or 0
        
        # Sinais de hoje
        hoje = datetime.now().date()
        sinais_hoje = db.query(func.count(Sinal.id)).filter(
            Sinal.nicho == nicho,
            func.date(Sinal.timestamp) == hoje
        ).scalar() or 0
        
        # Plataformas ativas
        plataformas_ativas = db.query(
            func.count(func.distinct(Sinal.plataforma))
        ).filter(
            Sinal.nicho == nicho
        ).scalar() or 0
        
        # Relevância média
        relevancia_media = db.query(
            func.avg(Sinal.relevancia)
        ).filter(
            Sinal.nicho == nicho
        ).scalar() or 0.0
        
        # Última coleta
        ultimo_sinal = db.query(Sinal).filter(
            Sinal.nicho == nicho
        ).order_by(
            Sinal.timestamp.desc()
        ).first()
        
        ultima_coleta = ultimo_sinal.timestamp.isoformat() if ultimo_sinal else datetime.now().isoformat()
        
        return {
            "total_sinais": total,
            "sinais_hoje": sinais_hoje,
            "plataformas_ativas": plataformas_ativas,
            "relevancia_media": round(float(relevancia_media), 2) if relevancia_media else 0.0,
            "ultima_coleta": ultima_coleta,
        }
    
    except Exception as e:
        log.error(f"Erro ao buscar estatísticas reais: {e}")
        # Fallback para mockados
        from makita.preview.gerador import get_estatisticas_mock
        return get_estatisticas_mock(nicho=nicho)


def get_preview_data(nicho: str, quantidade: int = 4) -> Dict[str, Any]:
    """
    Retorna dados completos para o preview (sinais + estatísticas).
    
    Args:
        nicho: ID do nicho
        quantidade: Quantidade de sinais
    
    Returns:
        Dict com sinais e estatísticas
    """
    sinais = buscar_sinais_reais(nicho=nicho, quantidade=quantidade)
    estatisticas = buscar_estatisticas_reais(nicho=nicho)
    
    return {
        "sinais": sinais,
        "estatisticas": estatisticas,
        "nicho": nicho,
        "is_real": len(sinais) > 0 and sinais[0].get("id") is not None,
    }


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DE PREVIEW COM DADOS REAIS ===\n")
    
    nicho = "saas"
    
    print(f"Buscando sinais reais para: {nicho}\n")
    
    # Buscar sinais
    sinais = buscar_sinais_reais(nicho=nicho, quantidade=4)
    
    if sinais:
        print(f"✅ Encontrados {len(sinais)} sinais reais:\n")
        for i, sinal in enumerate(sinais, 1):
            print(f"{i}. [{sinal['plataforma'].upper()}] {sinal['titulo']}")
            print(f"   Relevância: {sinal['relevancia']}")
            print(f"   Autor: {sinal['autor']}")
            print()
    else:
        print("⚠️ Nenhum sinal real encontrado, usando mockados\n")
        from makita.preview.gerador import gerar_sinais_mock
        sinais = gerar_sinais_mock(nicho=nicho, quantidade=4)
        for i, sinal in enumerate(sinais, 1):
            print(f"{i}. [{sinal['plataforma'].upper()}] {sinal['titulo']}")
    
    # Estatísticas
    print("\n=== ESTATÍSTICAS ===")
    stats = buscar_estatisticas_reais(nicho)
    for k, v in stats.items():
        print(f"{k}: {v}")