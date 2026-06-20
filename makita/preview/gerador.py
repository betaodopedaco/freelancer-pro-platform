"""
makita/preview/gerador.py
==========================
Gerador de sinais mockados para o "Momento Aha".

Uso:
    from makita.preview.gerador import gerar_sinais_mock
    
    sinais = gerar_sinais_mock(nicho="saas", quantidade=4)
"""

from typing import Dict, List, Any
import random
from datetime import datetime, timedelta

try:
    from logger import get_logger
    log = get_logger("preview.gerador")
except ImportError:
    import logging
    log = logging.getLogger("preview.gerador")
    log.setLevel(logging.INFO)


# Sinais mockados por nicho
SINAIS_MOCKADOS: Dict[str, List[Dict[str, Any]]] = {
    "imobiliario": [
        {
            "plataforma": "facebook",
            "tipo": "lead",
            "titulo": "Procurando apartamento 2 quartos em São Paulo",
            "descricao": "Alguém recomendou algum corretor? Estou buscando algo até R$ 400k",
            "autor": "Maria Silva",
            "relevancia": 0.95,
            "timestamp": datetime.now().isoformat(),
            "link": "https://facebook.com/post/123",
        },
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Qual a melhor região para investir em imóveis em 2024?",
            "descricao": "Estou pensando em comprar um apartamento para alugar. Alguém tem dicas?",
            "autor": "@joao_investidor",
            "relevancia": 0.88,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "link": "https://twitter.com/status/456",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Vale a pena comprar imóvel na planta?",
            "descricao": "Estou analisando um lançamento na zona sul. Alguém já comprou na planta?",
            "autor": "u/investidor_sp",
            "relevancia": 0.82,
            "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
            "link": "https://reddit.com/r/brasil/comments/789",
        },
        {
            "plataforma": "facebook",
            "tipo": "lead",
            "titulo": "Preciso de um arquiteto para reforma",
            "descricao": "Tenho um apartamento de 80m² para reformar. Alguém pode indicar?",
            "autor": "Carlos Mendes",
            "relevancia": 0.79,
            "timestamp": (datetime.now() - timedelta(hours=8)).isoformat(),
            "link": "https://facebook.com/post/321",
        },
    ],
    "saas": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Alguém conhece uma ferramenta de automação para WhatsApp?",
            "descricao": "Estou buscando algo para automatizar atendimento. Preciso de integração com CRM",
            "autor": "@empreendedor_tech",
            "relevancia": 0.96,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/abc",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Qual o melhor SaaS para gestão de projetos em 2024?",
            "descricao": "Nossa equipe está crescendo e precisamos de algo mais robusto que o Trello",
            "autor": "u/startup_founder",
            "relevancia": 0.91,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "link": "https://reddit.com/r/startups/comments/456",
        },
        {
            "plataforma": "hn",
            "tipo": "discussao",
            "titulo": "Show HN: Ferramenta open source para analytics",
            "descricao": "Acabei de lançar uma ferramenta de analytics focada em privacidade",
            "autor": "devopensource",
            "relevancia": 0.85,
            "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
            "link": "https://news.ycombinator.com/item?id=789",
        },
        {
            "plataforma": "twitter",
            "tipo": "lead",
            "titulo": "Procurando API de pagamento para SaaS",
            "descricao": "Preciso de uma solução com split de pagamento e assinaturas recorrentes",
            "autor": "@cto_startup",
            "relevancia": 0.83,
            "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
            "link": "https://twitter.com/status/def",
        },
    ],
    "ecommerce": [
        {
            "plataforma": "facebook",
            "tipo": "lead",
            "titulo": "Alguém indica fornecedor de produtos importados?",
            "descricao": "Quero abrir uma loja de produtos asiáticos. Preciso de fornecedor confiável",
            "autor": "Ana Costa",
            "relevancia": 0.94,
            "timestamp": datetime.now().isoformat(),
            "link": "https://facebook.com/post/xyz",
        },
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Qual plataforma usar para dropshipping no Brasil?",
            "descricao": "Estou começando e preciso de uma plataforma confiável com integração nuvemshop",
            "autor": "@ecommerce_br",
            "relevancia": 0.89,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "link": "https://twitter.com/status/uvw",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Dicas para aumentar conversão no checkout",
            "descricao": "Minha taxa de conversão caiu 30%. O que vocês fariam primeiro?",
            "autor": "u/lojista_virtual",
            "relevancia": 0.84,
            "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
            "link": "https://reddit.com/r/ecommerce/comments/123",
        },
        {
            "plataforma": "facebook",
            "tipo": "lead",
            "titulo": "Preciso de ajuda com Google Ads",
            "descricao": "Minhas campanhas não estão convertendo. Alguém pode me ajudar?",
            "autor": "Pedro Santos",
            "relevancia": 0.78,
            "timestamp": (datetime.now() - timedelta(hours=7)).isoformat(),
            "link": "https://facebook.com/post/456",
        },
    ],
    "crypto": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Qual a melhor exchange para iniciantes em 2024?",
            "descricao": "Estou começando a investir em cripto. Preciso de algo seguro e fácil",
            "autor": "@crypto_beginner",
            "relevancia": 0.95,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/btc1",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Análise técnica: Bitcoin vai romper os $70k?",
            "descricao": "Vamos discutir os indicadores e possíveis cenários para as próximas semanas",
            "autor": "u/trader_crypto",
            "relevancia": 0.90,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "link": "https://reddit.com/r/crypto/comments/btc2",
        },
        {
            "plataforma": "twitter",
            "tipo": "lead",
            "titulo": "Procurando desenvolvedor Solidity",
            "descricao": "Preciso de alguém para desenvolver um smart contract para NFT",
            "autor": "@web3_founder",
            "relevancia": 0.86,
            "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
            "link": "https://twitter.com/status/btc3",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "DeFi vale a pena em 2024?",
            "descricao": "Quais os riscos e oportunidades no mercado DeFi atualmente?",
            "autor": "u/investidor_defi",
            "relevancia": 0.81,
            "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
            "link": "https://reddit.com/r/defi/comments/btc4",
        },
    ],
    "marketing": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Qual a melhor estratégia de SEO para 2024?",
            "descricao": "Meu site não está ranqueando. Preciso de dicas atualizadas",
            "autor": "@marketeiro_digital",
            "relevancia": 0.94,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/seo1",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Copywriting: como escrever headlines que convertem?",
            "descricao": "Vamos compartilhar técnicas e exemplos práticos",
            "autor": "u/copywriter_pro",
            "relevancia": 0.89,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "link": "https://reddit.com/r/marketing/comments/seo2",
        },
        {
            "plataforma": "hn",
            "tipo": "discussao",
            "titulo": "Growth hacking: técnicas que realmente funcionam",
            "descricao": "Compartilhe cases de crescimento que você implementou",
            "autor": "growthhacker",
            "relevancia": 0.84,
            "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
            "link": "https://news.ycombinator.com/item?id=seo3",
        },
        {
            "plataforma": "twitter",
            "tipo": "lead",
            "titulo": "Preciso de um especialista em tráfego pago",
            "descricao": "Minhas campanhas no Meta Ads não estão performando",
            "autor": "@empreendedor_ads",
            "relevancia": 0.80,
            "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
            "link": "https://twitter.com/status/seo4",
        },
    ],
    "startup": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Como conseguir os primeiros 100 clientes?",
            "descricao": "Estamos lançando nosso MVP e precisamos de tração inicial",
            "autor": "@startup_founder_br",
            "relevancia": 0.95,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/start1",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Pitch deck: o que os investidores realmente querem ver?",
            "descricao": "Vamos discutir os elementos essenciais de um pitch deck de sucesso",
            "autor": "u/founder_serial",
            "relevancia": 0.90,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "link": "https://reddit.com/r/startups/comments/start2",
        },
        {
            "plataforma": "hn",
            "tipo": "discussao",
            "titulo": "Show HN: Nossa startup de IA para RH",
            "descricao": "Acabamos de sair do stealth mode. Gostaríamos de feedback",
            "autor": "founder_ai_hr",
            "relevancia": 0.85,
            "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
            "link": "https://news.ycombinator.com/item?id=start3",
        },
        {
            "plataforma": "twitter",
            "tipo": "lead",
            "titulo": "Buscando co-fundador técnico",
            "descricao": "Tenho a ideia e o mercado, preciso de alguém para desenvolver",
            "autor": "@tech_startup_br",
            "relevancia": 0.82,
            "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
            "link": "https://twitter.com/status/start4",
        },
    ],
    "ia": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Qual modelo de IA usar para atendimento ao cliente?",
            "descricao": "Estou buscando uma solução de chatbot com IA para meu e-commerce",
            "autor": "@ia_enthusiast",
            "relevancia": 0.96,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/ia1",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "GPT-4 vs Claude: qual é melhor para código?",
            "descricao": "Vamos comparar os dois modelos em tarefas de programação",
            "autor": "u/dev_ai",
            "relevancia": 0.91,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "link": "https://reddit.com/r/artificial/comments/ia2",
        },
        {
            "plataforma": "hn",
            "tipo": "discussao",
            "titulo": "Show HN: Ferramenta open source de IA generativa",
            "descricao": "Acabei de lançar uma alternativa open source ao Midjourney",
            "autor": "open_source_ai",
            "relevancia": 0.87,
            "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
            "link": "https://news.ycombinator.com/item?id=ia3",
        },
        {
            "plataforma": "twitter",
            "tipo": "lead",
            "titulo": "Preciso de consultoria em IA para meu negócio",
            "descricao": "Quero implementar IA na minha operação mas não sei por onde começar",
            "autor": "@business_ia",
            "relevancia": 0.83,
            "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
            "link": "https://twitter.com/status/ia4",
        },
    ],
    "personalizado": [
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Exemplo de sinal personalizado 1",
            "descricao": "Este é um exemplo de sinal para nicho personalizado",
            "autor": "@usuario_exemplo",
            "relevancia": 0.90,
            "timestamp": datetime.now().isoformat(),
            "link": "https://twitter.com/status/custom1",
        },
        {
            "plataforma": "facebook",
            "tipo": "lead",
            "titulo": "Exemplo de sinal personalizado 2",
            "descricao": "Outro exemplo para demonstrar o funcionamento",
            "autor": "Usuário Exemplo",
            "relevancia": 0.85,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "link": "https://facebook.com/post/custom2",
        },
        {
            "plataforma": "reddit",
            "tipo": "discussao",
            "titulo": "Exemplo de sinal personalizado 3",
            "descricao": "Mais um exemplo para o preview",
            "autor": "u/usuario_custom",
            "relevancia": 0.80,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "link": "https://reddit.com/r/brasil/comments/custom3",
        },
        {
            "plataforma": "twitter",
            "tipo": "pergunta",
            "titulo": "Exemplo de sinal personalizado 4",
            "descricao": "Último exemplo do preview",
            "autor": "@custom_user",
            "relevancia": 0.75,
            "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
            "link": "https://twitter.com/status/custom4",
        },
    ],
}


def gerar_sinais_mock(
    nicho: str = "personalizado",
    quantidade: int = 4,
    plataformas: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Gera sinais mockados para o momento aha.
    
    Args:
        nicho: ID do nicho (ex: "saas", "imobiliario")
        quantidade: Quantidade de sinais (padrão: 4)
        plataformas: Lista de plataformas para filtrar (opcional)
    
    Returns:
        Lista de sinais mockados
    """
    # Buscar sinais do nicho
    if nicho not in SINAIS_MOCKADOS:
        log.warning(f"Nicho '{nicho}' não encontrado, usando 'personalizado'")
        nicho = "personalizado"
    
    sinais = SINAIS_MOCKADOS[nicho].copy()
    
    # Filtrar por plataformas se fornecido
    if plataformas:
        sinais = [s for s in sinais if s["plataforma"] in plataformas]
    
    # Limitar quantidade
    sinais = sinais[:quantidade]
    
    # Adicionar variação de timestamp
    for i, sinal in enumerate(sinais):
        variacao = timedelta(minutes=random.randint(0, 30))
        sinal["timestamp"] = (datetime.now() - variacao).isoformat()
    
    log.info(f"Gerados {len(sinais)} sinais mockados para nicho '{nicho}'")
    
    return sinais


def gerar_sinal_aleatorio(nicho: str = "personalizado") -> Dict[str, Any]:
    """
    Gera um sinal mockado aleatório.
    
    Args:
        nicho: ID do nicho
    
    Returns:
        Sinal mockado
    """
    sinais = gerar_sinais_mock(nicho=nicho, quantidade=1)
    return sinais[0] if sinais else {}


def get_estatisticas_mock(nicho: str = "personalizado") -> Dict[str, Any]:
    """
    Retorna estatísticas mockadas para o preview.
    
    Args:
        nicho: ID do nicho
    
    Returns:
        Dict com estatísticas
    """
    return {
        "total_sinais": random.randint(150, 300),
        "sinais_hoje": random.randint(8, 15),
        "plataformas_ativas": random.randint(3, 5),
        "relevancia_media": round(random.uniform(0.75, 0.95), 2),
        "ultima_coleta": datetime.now().isoformat(),
    }


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO GERADOR DE PREVIEW ===\n")
    
    # Gerar sinais para SaaS
    print("Gerando 4 sinais para SaaS...")
    sinais = gerar_sinais_mock(nicho="saas", quantidade=4)
    
    for i, sinal in enumerate(sinais, 1):
        print(f"\n{i}. [{sinal['plataforma'].upper()}] {sinal['titulo']}")
        print(f"   Relevância: {sinal['relevancia']}")
        print(f"   Autor: {sinal['autor']}")
    
    # Estatísticas
    print("\n=== ESTATÍSTICAS ===")
    stats = get_estatisticas_mock("saas")
    for k, v in stats.items():
        print(f"{k}: {v}")