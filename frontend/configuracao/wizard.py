"""
makita/configuracao/wizard.py
==============================
Wizard de configuração guiada para o usuário.

Uso:
    from makita.configuracao.wizard import WizardConfiguracao
    
    wizard = WizardConfiguracao(usuario_id="123")
    await wizard.iniciar()
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    from logger import get_logger
    log = get_logger("configuracao.wizard")
except ImportError:
    import logging
    log = logging.getLogger("configuracao.wizard")
    log.setLevel(logging.INFO)


class EtapaWizard(Enum):
    """Etapas do wizard de configuração."""
    NICHOS = "nichos"
    KEYWORDS = "keywords"
    PLATAFORMAS = "plataformas"
    FREQUENCIA = "frequencia"
    RELEVANCIA = "relevancia"
    CONCLUIR = "concluir"


@dataclass
class EstadoWizard:
    """Estado do wizard para um usuário."""
    usuario_id: str
    etapa_atual: EtapaWizard = EtapaWizard.NICHOS
    nicho_escolhido: Optional[str] = None
    keywords_personalizadas: List[str] = field(default_factory=list)
    plataformas_escolhidas: List[str] = field(default_factory=list)
    frequencia_coleta: int = 3600  # 1 hora em segundos
    relevancia_minima: float = 0.7
    concluido: bool = False


class WizardConfiguracao:
    """
    Wizard de configuração guiada.
    
    Guia o usuário através de etapas simples:
    1. Escolha de nicho
    2. Configuração de keywords
    3. Seleção de plataformas
    4. Frequência de coleta
    5. Relevância mínima
    """
    
    def __init__(self, usuario_id: str):
        """
        Inicializa o wizard.
        
        Args:
            usuario_id: ID do usuário
        """
        self.usuario_id = usuario_id
        self.estado = EstadoWizard(usuario_id=usuario_id)
    
    def get_etapa_atual(self) -> EtapaWizard:
        """Retorna a etapa atual do wizard."""
        return self.estado.etapa_atual
    
    def get_progresso(self) -> Dict[str, Any]:
        """
        Retorna o progresso atual do wizard.
        
        Returns:
            Dict com etapa atual, total de etapas e percentual
        """
        etapas = list(EtapaWizard)
        atual_idx = etapas.index(self.estado.etapa_atual)
        
        return {
            "etapa_atual": self.estado.etapa_atual.value,
            "etapa_numero": atual_idx + 1,
            "total_etapas": len(etapas),
            "percentual": int((atual_idx + 1) / len(etapas) * 100),
        }
    
    def get_opcoes_etapa(self) -> Dict[str, Any]:
        """
        Retorna as opções disponíveis para a etapa atual.
        
        Returns:
            Dict com opções da etapa
        """
        from makita.nichos.templates import list_templates, get_template
        
        if self.estado.etapa_atual == EtapaWizard.NICHOS:
            templates = list_templates()
            return {
                "tipo": "selecao_unica",
                "opcoes": templates,
                "titulo": "Escolha seu nicho",
                "descricao": "Selecione o nicho que melhor se adapta ao seu negócio",
            }
        
        elif self.estado.etapa_atual == EtapaWizard.KEYWORDS:
            if not self.estado.nicho_escolhido:
                raise ValueError("Nicho não escolhido")
            
            template = get_template(self.estado.nicho_escolhido)
            return {
                "tipo": "selecao_multipla",
                "opcoes": template["keywords"],
                "padrao": template["keywords"][:5],  # Primeiras 5 como padrão
                "titulo": "Quais keywords você quer monitorar?",
                "descricao": "Escolha de 3 a 10 palavras-chave",
                "min_selecao": 3,
                "max_selecao": 10,
            }
        
        elif self.estado.etapa_atual == EtapaWizard.PLATAFORMAS:
            if not self.estado.nicho_escolhido:
                raise ValueError("Nicho não escolhido")
            
            template = get_template(self.estado.nicho_escolhido)
            todas_plataformas = [
                {"id": "facebook", "nome": "Facebook", "icone": "📘"},
                {"id": "twitter", "nome": "Twitter/X", "icone": "🐦"},
                {"id": "reddit", "nome": "Reddit", "icone": "🔴"},
                {"id": "bluesky", "nome": "Bluesky", "icone": "🦋"},
                {"id": "hn", "nome": "Hacker News", "icone": "📰"},
            ]
            
            return {
                "tipo": "selecao_multipla",
                "opcoes": todas_plataformas,
                "padrao": template["plataformas"],
                "titulo": "Onde você quer monitorar?",
                "descricao": "Selecione as plataformas para coletar sinais",
                "min_selecao": 1,
                "max_selecao": 5,
            }
        
        elif self.estado.etapa_atual == EtapaWizard.FREQUENCIA:
            return {
                "tipo": "slider",
                "min": 900,  # 15 min
                "max": 14400,  # 4 horas
                "padrao": 3600,  # 1 hora
                "step": 900,  # 15 min
                "unidade": "segundos",
                "opcoes_predefinidas": [
                    {"valor": 900, "label": "A cada 15 min"},
                    {"valor": 1800, "label": "A cada 30 min"},
                    {"valor": 3600, "label": "A cada 1 hora"},
                    {"valor": 7200, "label": "A cada 2 horas"},
                    {"valor": 14400, "label": "A cada 4 horas"},
                ],
                "titulo": "Com que frequência coletar?",
                "descricao": "Menor frequência = mais dados, maior custo",
            }
        
        elif self.estado.etapa_atual == EtapaWizard.RELEVANCIA:
            return {
                "tipo": "slider",
                "min": 0.5,
                "max": 1.0,
                "padrao": 0.7,
                "step": 0.05,
                "unidade": "score",
                "opcoes_predefinidas": [
                    {"valor": 0.5, "label": "Baixo (mais resultados)"},
                    {"valor": 0.7, "label": "Médio (balanceado)"},
                    {"valor": 0.9, "label": "Alto (apenas ótimos)"},
                ],
                "titulo": "Qual a relevância mínima?",
                "descricao": "Quão relevante deve ser um sinal para ser entregue",
            }
        
        elif self.estado.etapa_atual == EtapaWizard.CONCLUIR:
            return {
                "tipo": "resumo",
                "titulo": "Tudo pronto!",
                "descricao": "Revise suas configurações antes de começar",
            }
        
        raise ValueError(f"Etapa desconhecida: {self.estado.etapa_atual}")
    
    def processar_etapa(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa os dados da etapa atual e avança.
        
        Args:
            dados: Dados enviados pelo usuário
        
        Returns:
            Dict com resultado do processamento
        """
        from makita.nichos.templates import get_template
        
        try:
            if self.estado.etapa_atual == EtapaWizard.NICHOS:
                nicho_id = dados.get("nicho_id")
                if not nicho_id:
                    raise ValueError("Selecione um nicho")
                
                template = get_template(nicho_id)
                self.estado.nicho_escolhido = nicho_id
                log.info(f"Usuário {self.usuario_id} escolheu nicho: {nicho_id}")
            
            elif self.estado.etapa_atual == EtapaWizard.KEYWORDS:
                keywords = dados.get("keywords", [])
                
                if len(keywords) < 3:
                    raise ValueError("Selecione pelo menos 3 keywords")
                
                if len(keywords) > 10:
                    raise ValueError("Selecione no máximo 10 keywords")
                
                self.estado.keywords_personalizadas = keywords
                log.info(f"Usuário {self.usuario_id} escolheu {len(keywords)} keywords")
            
            elif self.estado.etapa_atual == EtapaWizard.PLATAFORMAS:
                plataformas = dados.get("plataformas", [])
                
                if not plataformas:
                    raise ValueError("Selecione pelo menos 1 plataforma")
                
                self.estado.plataformas_escolhidas = plataformas
                log.info(f"Usuário {self.usuario_id} escolheu plataformas: {plataformas}")
            
            elif self.estado.etapa_atual == EtapaWizard.FREQUENCIA:
                frequencia = dados.get("frequencia")
                
                if not frequencia or frequencia < 900 or frequencia > 14400:
                    raise ValueError("Frequência inválida (deve ser entre 15min e 4h)")
                
                self.estado.frequencia_coleta = frequencia
                log.info(f"Usuário {self.usuario_id} definiu frequência: {frequencia}s")
            
            elif self.estado.etapa_atual == EtapaWizard.RELEVANCIA:
                relevancia = dados.get("relevancia")
                
                if relevancia is None or relevancia < 0.5 or relevancia > 1.0:
                    raise ValueError("Relevância inválida (deve ser entre 0.5 e 1.0)")
                
                self.estado.relevancia_minima = relevancia
                log.info(f"Usuário {self.usuario_id} definiu relevância mínima: {relevancia}")
            
            elif self.estado.etapa_atual == EtapaWizard.CONCLUIR:
                self.estado.concluido = True
                log.info(f"Usuário {self.usuario_id} concluiu o wizard")
            
            # Avançar para próxima etapa
            self._avancar_etapa()
            
            return {
                "sucesso": True,
                "proxima_etapa": self.estado.etapa_atual.value,
                "progresso": self.get_progresso(),
            }
        
        except ValueError as e:
            log.error(f"Erro no wizard para usuário {self.usuario_id}: {e}")
            return {
                "sucesso": False,
                "erro": str(e),
                "etapa_atual": self.estado.etapa_atual.value,
            }
    
    def _avancar_etapa(self) -> None:
        """Avança para a próxima etapa do wizard."""
        etapas = list(EtapaWizard)
        idx_atual = etapas.index(self.estado.etapa_atual)
        
        if idx_atual < len(etapas) - 1:
            self.estado.etapa_atual = etapas[idx_atual + 1]
        else:
            self.estado.etapa_atual = EtapaWizard.CONCLUIR
    
    def get_configuracao_final(self) -> Dict[str, Any]:
        """
        Retorna a configuração final do usuário.
        
        Returns:
            Dict com todas as configurações escolhidas
        """
        if not self.estado.concluido:
            raise ValueError("Wizard não foi concluído")
        
        from makita.nichos.templates import get_template
        
        template = get_template(self.estado.nicho_escolhido)
        
        return {
            "usuario_id": self.usuario_id,
            "nicho": {
                "id": self.estado.nicho_escolhido,
                "nome": template["nome"],
                "icone": template["icone"],
            },
            "keywords": self.estado.keywords_personalizadas,
            "plataformas": self.estado.plataformas_escolhidas,
            "configuracoes": {
                "frequencia_coleta": self.estado.frequencia_coleta,
                "relevancia_minima": self.estado.relevancia_minima,
            },
            "criado_em": self.estado.criado_em if hasattr(self.estado, 'criado_em') else None,
        }
    
    def pular_etapa(self) -> None:
        """Pula a etapa atual (usa valores padrão)."""
        from makita.nichos.templates import get_template
        
        if self.estado.etapa_atual == EtapaWizard.KEYWORDS:
            template = get_template(self.estado.nicho_escolhido)
            self.estado.keywords_personalizadas = template["keywords"][:5]
        
        elif self.estado.etapa_atual == EtapaWizard.PLATAFORMAS:
            template = get_template(self.estado.nicho_escolhido)
            self.estado.plataformas_escolhidas = template["plataformas"]
        
        elif self.estado.etapa_atual == EtapaWizard.FREQUENCIA:
            template = get_template(self.estado.nicho_escolhido)
            defaults = template["smart_defaults"]
            self.estado.frequencia_coleta = defaults["frequencia_coleta"]
        
        elif self.estado.etapa_atual == EtapaWizard.RELEVANCIA:
            template = get_template(self.estado.nicho_escolhido)
            defaults = template["smart_defaults"]
            self.estado.relevancia_minima = defaults["relevancia_minima"]
        
        self._avancar_etapa()
        log.info(f"Usuário {self.usuario_id} pulou etapa: {self.estado.etapa_atual}")


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO WIZARD ===\n")
    
    wizard = WizardConfiguracao(usuario_id="teste_123")
    
    # Etapa 1: Nichos
    print(f"Etapa: {wizard.get_etapa_atual().value}")
    opcoes = wizard.get_opcoes_etapa()
    print(f"Título: {opcoes['titulo']}")
    print(f"Opções: {[o['nome'] for o in opcoes['opcoes']]}\n")
    
    # Processar escolha
    resultado = wizard.processar_etapa({"nicho_id": "saas"})
    print(f"Resultado: {resultado}\n")
    
    # Etapa 2: Keywords
    print(f"Etapa: {wizard.get_etapa_atual().value}")
    opcoes = wizard.get_opcoes_etapa()
    print(f"Título: {opcoes['titulo']}")
    print(f"Keywords padrão: {opcoes['padrao']}\n")
    
    # Processar keywords
    resultado = wizard.processar_etapa({
        "keywords": ["software", "SaaS", "automação"]
    })
    print(f"Resultado: {resultado}\n")
    
    # Progresso
    print(f"Progresso: {wizard.get_progresso()}")