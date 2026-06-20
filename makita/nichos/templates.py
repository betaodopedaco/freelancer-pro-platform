"""
makita/nichos/templates.py
==========================
Templates de nicho com keywords pré-configuradas e smart defaults.

Uso:
    from makita.nichos.templates import get_template, list_templates
    
    # Listar todos os templates
    templates = list_templates()
    
    # Obter um template específico
    template = get_template("imobiliario")
    
    # Usar as keywords
    keywords = template["keywords"]
"""

from typing import Dict, List, Any


# Templates pré-configurados por nicho
NICHO_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "imobiliario": {
        "id": "imobiliario",
        "nome": "Imobiliário",
        "descricao": "Imóveis, aluguéis, vendas e investimentos",
        "icone": "🏠",
        "keywords": [
            "imóveis à venda",
            "apartamento",
            "casa",
            "terreno",
            "aluguel",
            "financiamento",
            "construção",
            "reforma",
            "imobiliária",
            "corretor",
        ],
        "plataformas": ["facebook", "twitter", "reddit", "bluesky"],
        "smart_defaults": {
            "max_palavras": 10,
            "frequencia_coleta": 3600,  # 1 hora
            "relevancia_minima": 0.7,
        },
    },
    "saas": {
        "id": "saas",
        "nome": "SaaS / Software",
        "descricao": "Softwares, ferramentas, automação e produtividade",
        "icone": "☁️",
        "keywords": [
            "software",
            "ferramenta",
            "automação",
            "produtividade",
            "SaaS",
            "API",
            "integração",
            "dashboard",
            "analytics",
            "cloud",
        ],
        "plataformas": ["twitter", "reddit", "bluesky", "hn"],
        "smart_defaults": {
            "max_palavras": 15,
            "frequencia_coleta": 1800,  # 30 min
            "relevancia_minima": 0.6,
        },
    },
    "ecommerce": {
        "id": "ecommerce",
        "nome": "E-commerce",
        "descricao": "Lojas virtuais, vendas online, dropshipping",
        "icone": "🛒",
        "keywords": [
            "e-commerce",
            "loja virtual",
            "vendas online",
            "dropshipping",
            "produto",
            "checkout",
            "pagamento",
            "frete",
            "conversão",
            "marketing digital",
        ],
        "plataformas": ["facebook", "twitter", "reddit"],
        "smart_defaults": {
            "max_palavras": 12,
            "frequencia_coleta": 2400,  # 40 min
            "relevancia_minima": 0.65,
        },
    },
    "crypto": {
        "id": "crypto",
        "nome": "Crypto / Web3",
        "descricao": "Criptomoedas, DeFi, NFTs, blockchain",
        "icone": "₿",
        "keywords": [
            "bitcoin",
            "ethereum",
            "criptomoeda",
            "DeFi",
            "NFT",
            "blockchain",
            "trading",
            "investimento",
            "altcoin",
            "web3",
        ],
        "plataformas": ["twitter", "reddit", "bluesky"],
        "smart_defaults": {
            "max_palavras": 20,
            "frequencia_coleta": 900,  # 15 min
            "relevancia_minima": 0.5,
        },
    },
    "marketing": {
        "id": "marketing",
        "nome": "Marketing Digital",
        "descricao": "Tráfego, SEO, conteúdo, redes sociais",
        "icone": "📊",
        "keywords": [
            "marketing digital",
            "SEO",
            "tráfego",
            "conteúdo",
            "redes sociais",
            "copywriting",
            "funil",
            "lead",
            "conversão",
            "ads",
        ],
        "plataformas": ["twitter", "reddit", "bluesky", "hn"],
        "smart_defaults": {
            "max_palavras": 15,
            "frequencia_coleta": 1800,  # 30 min
            "relevancia_minima": 0.6,
        },
    },
    "startup": {
        "id": "startup",
        "nome": "Startups",
        "descricao": "Empreendedorismo, investimentos, pitch",
        "icone": "🚀",
        "keywords": [
            "startup",
            "empreendedor",
            "investimento",
            "pitch",
            "MVP",
            "growth",
            "escalabilidade",
            "venture capital",
            "seed",
            "series A",
        ],
        "plataformas": ["twitter", "reddit", "bluesky", "hn"],
        "smart_defaults": {
            "max_palavras": 12,
            "frequencia_coleta": 2400,  # 40 min
            "relevancia_minima": 0.65,
        },
    },
    "ia": {
        "id": "ia",
        "nome": "Inteligência Artificial",
        "descricao": "IA, ML, LLMs, automação inteligente",
        "icone": "🤖",
        "keywords": [
            "inteligência artificial",
            "machine learning",
            "LLM",
            "GPT",
            "automação",
            "IA generativa",
            "deep learning",
            "neural",
            "chatbot",
            "OpenAI",
        ],
        "plataformas": ["twitter", "reddit", "bluesky", "hn"],
        "smart_defaults": {
            "max_palavras": 18,
            "frequencia_coleta": 1200,  # 20 min
            "relevancia_minima": 0.55,
        },
    },
    "personalizado": {
        "id": "personalizado",
        "nome": "Personalizado",
        "descricao": "Crie seu próprio conjunto de keywords",
        "icone": "⚙️",
        "keywords": [],
        "plataformas": ["facebook", "twitter", "reddit", "bluesky", "hn"],
        "smart_defaults": {
            "max_palavras": 10,
            "frequencia_coleta": 3600,  # 1 hora
            "relevancia_minima": 0.7,
        },
    },
}


def list_templates() -> List[Dict[str, Any]]:
    """
    Lista todos os templates disponíveis.
    
    Returns:
        Lista de templates com id, nome, descrição e ícone
    """
    return [
        {
            "id": t["id"],
            "nome": t["nome"],
            "descricao": t["descricao"],
            "icone": t["icone"],
        }
        for t in NICHO_TEMPLATES.values()
    ]


def get_template(nicho_id: str) -> Dict[str, Any]:
    """
    Obtém um template específico por ID.
    
    Args:
        nicho_id: ID do nicho (ex: "imobiliario", "saas")
    
    Returns:
        Template completo com keywords, plataformas e smart defaults
    
    Raises:
        ValueError: Se o nicho não existir
    """
    if nicho_id not in NICHO_TEMPLATES:
        raise ValueError(
            f"Nicho '{nicho_id}' não encontrado. "
            f"Nichos disponíveis: {list(NICHO_TEMPLATES.keys())}"
        )
    
    return NICHO_TEMPLATES[nicho_id]


def get_keywords(nicho_id: str) -> List[str]:
    """
    Obtém apenas as keywords de um template.
    
    Args:
        nicho_id: ID do nicho
    
    Returns:
        Lista de keywords
    """
    template = get_template(nicho_id)
    return template["keywords"]


def get_smart_defaults(nicho_id: str) -> Dict[str, Any]:
    """
    Obtém os smart defaults de um template.
    
    Args:
        nicho_id: ID do nicho
    
    Returns:
        Dict com max_palavras, frequencia_coleta, relevancia_minima
    """
    template = get_template(nicho_id)
    return template["smart_defaults"]


def get_plataformas(nicho_id: str) -> List[str]:
    """
    Obtém as plataformas recomendadas para um nicho.
    
    Args:
        nicho_id: ID do nicho
    
    Returns:
        Lista de plataformas (facebook, twitter, reddit, bluesky, hn)
    """
    template = get_template(nicho_id)
    return template["plataformas"]


def search_templates(query: str) -> List[Dict[str, Any]]:
    """
    Busca templates por nome ou descrição.
    
    Args:
        query: Termo de busca (ex: "imóvel", "software")
    
    Returns:
        Lista de templates que correspondem à busca
    """
    query_lower = query.lower()
    results = []
    
    for template in NICHO_TEMPLATES.values():
        # Busca no nome, descrição e keywords
        if (
            query_lower in template["nome"].lower()
            or query_lower in template["descricao"].lower()
            or any(query_lower in kw.lower() for kw in template["keywords"])
        ):
            results.append({
                "id": template["id"],
                "nome": template["nome"],
                "descricao": template["descricao"],
                "icone": template["icone"],
            })
    
    return results


# Exemplo de uso
if __name__ == "__main__":
    print("=== TEMPLATES DISPONÍVEIS ===")
    templates = list_templates()
    for t in templates:
        print(f"{t['icone']} {t['nome']}: {t['descricao']}")
    
    print("\n=== EXEMPLO: IMOBILIÁRIO ===")
    template = get_template("imobiliario")
    print(f"Keywords: {template['keywords']}")
    print(f"Plataformas: {template['plataformas']}")
    print(f"Smart defaults: {template['smart_defaults']}")
    
    print("\n=== BUSCA: 'vendas' ===")
    results = search_templates("vendas")
    for r in results:
        print(f"{r['icone']} {r['nome']}")