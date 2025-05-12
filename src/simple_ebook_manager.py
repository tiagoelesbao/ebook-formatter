import os
import re
import time
import yaml
import anthropic
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
import shutil
import sys

# Configurar caminhos para encontrar módulos na estrutura existente
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tente importar bibliotecas opcionais com tratamento de erros mais robusto
DOCX2TXT_AVAILABLE = False
PYPANDOC_AVAILABLE = False
DOCX_AVAILABLE = False

try:
    import docx2txt
    DOCX2TXT_AVAILABLE = True
except ImportError:
    pass

try:
    import pypandoc
    PYPANDOC_AVAILABLE = True
except ImportError:
    pass

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    pass

# Importando frontmatter apenas para verificar se está disponível
FRONTMATTER_AVAILABLE = False
try:
    import frontmatter
    FRONTMATTER_AVAILABLE = True
except ImportError:
    pass

console = Console()

class SimpleEbookManager:
    def __init__(self, config_path='config.yaml'):
        """Inicializa o gerenciador de ebooks com configurações"""
        # Configuração de diretórios usando a estrutura existente
        self.base_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.temp_dir = self.base_dir / "temp"
        self.output_dir = self.base_dir / "output"
        self.content_dir = self.base_dir / "content"
        self.logs_dir = self.base_dir / "logs"
        self.src_dir = self.base_dir / "src"
        self.styles_dir = self.src_dir / "styles"
        self.templates_dir = self.src_dir / "templates"
        
        # Verificando se os diretórios necessários existem
        self._ensure_directories()
        
        # Carregando configurações e configurando o cliente
        self.load_config(config_path)
        self.setup_anthropic_client()
        self.log_file = self.logs_dir / f"simple_ebook_manager_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_message("Inicialização do SimpleEbookManager")
        
    def _ensure_directories(self):
        """Garante que todos os diretórios necessários existam"""
        try:
            self.temp_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)
            
            # Verifica e cria os diretórios de conteúdo
            self.content_dir.mkdir(exist_ok=True)
            (self.content_dir / "original").mkdir(exist_ok=True)
            (self.content_dir / "formatted").mkdir(exist_ok=True)
            
            # Verifica e cria os diretórios de saída
            self.output_dir.mkdir(exist_ok=True)
            (self.output_dir / "epub").mkdir(exist_ok=True)
            (self.output_dir / "pdf").mkdir(exist_ok=True)
            (self.output_dir / "html").mkdir(exist_ok=True)
            
            # Verifica e cria os diretórios de estilos e templates
            self.styles_dir.mkdir(exist_ok=True, parents=True)
            self.templates_dir.mkdir(exist_ok=True, parents=True)
            
            console.print("[green]✓ Diretórios verificados e criados[/green]")
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao criar diretórios:[/bold red] {str(e)}")
            raise
        
    def load_config(self, config_path):
        """Carrega configurações do arquivo YAML"""
        try:
            # Primeiro, tenta o caminho fornecido
            if os.path.exists(config_path):
                config_file = config_path
            else:
                # Tenta o caminho relativo à raiz do projeto
                config_file = self.base_dir / config_path
                
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                console.print(f"[bold green]✓ Configurações carregadas de {config_file}[/bold green]")
            else:
                # Configuração padrão se o arquivo não existir
                self.config = {
                    "ebook": {
                        "title": "Ebook",
                        "subtitle": "",
                        "author": "",
                        "language": "pt-BR"
                    },
                    "ai": {
                        "model": "claude-3-opus-20240229",
                        "temperature": 0.1,
                        "max_tokens": 4000
                    },
                    "formatting": {
                        "word_count_tolerance": 5
                    }
                }
                console.print("[yellow]⚠ Arquivo de configuração não encontrado. Usando configuração padrão.[/yellow]")
                
                # Salva a configuração padrão para referência futura
                with open(self.base_dir / "config.yaml", 'w', encoding='utf-8') as f:
                    yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
                console.print(f"[blue]ℹ Configuração padrão salva em {self.base_dir / 'config.yaml'}[/blue]")
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao carregar configurações:[/bold red] {str(e)}")
            self.config = {
                "ebook": {"title": "Ebook"}, 
                "ai": {"model": "claude-3-opus-20240229"}
            }
            self.log_message(f"Erro ao carregar configurações: {str(e)}", "ERROR")
    
    def setup_anthropic_client(self):
        """Configura o cliente da API Anthropic"""
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                console.print("[bold yellow]⚠ Aviso: ANTHROPIC_API_KEY não encontrada no ambiente[/bold yellow]")
                api_key = console.input("[bold]Por favor, forneça sua chave API agora: [/bold]")
                os.environ["ANTHROPIC_API_KEY"] = api_key
            
            self.client = anthropic.Anthropic(api_key=api_key)
            console.print("[bold green]✓ Cliente Anthropic configurado com sucesso[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao configurar cliente Anthropic:[/bold red] {str(e)}")
            self.log_message(f"Erro ao configurar cliente Anthropic: {str(e)}", "ERROR")
            raise
    
    def log_message(self, message, level="INFO"):
        """Registra uma mensagem no arquivo de log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} [{level}] {message}\n")
        except Exception as e:
            console.print(f"[yellow]⚠ Erro ao escrever no log: {str(e)}[/yellow]")
    
    def process_document(self, filepath, title=None, author=None, output_format='epub', 
                         output_file=None, headings_pattern=None):
        """
        Processa um documento DOCX e o converte em um ebook formatado
        
        Args:
            filepath: Caminho para o arquivo a ser processado
            title: Título do ebook (opcional)
            author: Autor do ebook (opcional)
            output_format: Formato de saída (epub, pdf, html)
            output_file: Caminho para o arquivo de saída (opcional)
            headings_pattern: Padrão regex para identificar títulos (opcional)
            
        Returns:
            bool: True se processado com sucesso, False caso contrário
        """
        console.print(f"\n[bold cyan]Processando documento:[/bold cyan] {filepath}")
        self.log_message(f"Iniciando processamento do documento: {filepath}")
        
        try:
            # 1. Verificar se o arquivo existe
            if not os.path.exists(filepath):
                console.print(f"[bold red]✘ Arquivo não encontrado:[/bold red] {filepath}")
                return False
                
            # 2. Extrair texto do documento
            document_text = self._extract_text_from_document(filepath)
            if not document_text:
                return False
                
            # 3. Extrair metadados do documento (se não fornecidos)
            document_info = self._extract_document_info(filepath, document_text, title, author)
            
            # 4. Formatar o documento com IA
            formatted_text = self._format_document_with_ai(document_text, document_info, headings_pattern)
            if not formatted_text:
                return False
                
            # 5. Salvar o documento formatado em Markdown
            markdown_filepath = self._save_formatted_markdown(formatted_text, document_info)
            if not markdown_filepath:
                return False
                
            # 6. Gerar o ebook no formato solicitado
            if output_file:
                # Se o caminho de saída for absoluto, use-o diretamente
                if os.path.isabs(output_file):
                    output_path = output_file
                else:
                    # Se for relativo, considere-o relativo ao diretório output/formato
                    output_path = str(self.output_dir / output_format / os.path.basename(output_file))
            else:
                sanitized_title = re.sub(r'[^\w\s-]', '', document_info['title']).replace(' ', '_').lower()
                output_path = str(self.output_dir / output_format / f"{sanitized_title}.{output_format}")
                
            success = self._generate_ebook(markdown_filepath, output_path, output_format, document_info)
            
            if success:
                console.print(f"[bold green]✓ Ebook gerado com sucesso:[/bold green] {output_path}")
                # Copiar o arquivo para o diretório atual para facilitar o acesso
                try:
                    output_filename = os.path.basename(output_path)
                    current_dir_copy = os.path.join(os.getcwd(), output_filename)
                    shutil.copy2(output_path, current_dir_copy)
                    console.print(f"[blue]ℹ Arquivo copiado para diretório atual:[/blue] {current_dir_copy}")
                except Exception as e:
                    console.print(f"[yellow]⚠ Não foi possível copiar para o diretório atual: {str(e)}[/yellow]")
                return True
            else:
                console.print("[bold red]✘ Falha ao gerar ebook[/bold red]")
                return False
                
        except Exception as e:
            console.print(f"[bold red]✘ Erro durante o processamento:[/bold red] {str(e)}")
            self.log_message(f"Erro durante o processamento: {str(e)}", "ERROR")
            import traceback
            self.log_message(traceback.format_exc(), "ERROR")
            console.print("[yellow]⚠ Verifique o arquivo de log para mais detalhes[/yellow]")
            return False
            
    def _extract_text_from_document(self, filepath):
        """Extrai o texto de um documento"""
        console.print("[cyan]ℹ Extraindo texto do documento...[/cyan]")
        
        try:
            # Detecta o tipo de arquivo pela extensão
            file_ext = os.path.splitext(filepath)[1].lower()
            
            content = ""
            if file_ext == '.docx':
                # Tenta vários métodos para processar o DOCX
                if DOCX2TXT_AVAILABLE:
                    try:
                        content = docx2txt.process(filepath)
                        console.print("[green]✓ Arquivo DOCX processado com docx2txt[/green]")
                    except Exception as e:
                        console.print(f"[yellow]⚠ Erro ao processar com docx2txt: {str(e)}. Tentando outro método...[/yellow]")
                        content = ""
                
                # Se docx2txt falhou ou não está disponível, tenta python-docx
                if not content and DOCX_AVAILABLE:
                    try:
                        doc = Document(filepath)
                        content = "\n".join([para.text for para in doc.paragraphs])
                        console.print("[green]✓ Arquivo DOCX processado com python-docx[/green]")
                    except Exception as e:
                        console.print(f"[yellow]⚠ Erro ao processar com python-docx: {str(e)}[/yellow]")
                        content = ""
                
                # Se nenhum método funcionou
                if not content:
                    if not DOCX2TXT_AVAILABLE and not DOCX_AVAILABLE:
                        console.print("[bold red]✘ Erro: Instale docx2txt ou python-docx para processar arquivos DOCX[/bold red]")
                        console.print("[blue]pip install docx2txt[/blue] ou [blue]pip install python-docx[/blue]")
                        return None
                    else:
                        console.print("[bold red]✘ Não foi possível processar o arquivo DOCX com os métodos disponíveis[/bold red]")
                        return None
                        
            elif file_ext == '.txt' or file_ext == '.md':
                # Para arquivos de texto, usar codificação UTF-8
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    console.print("[green]✓ Arquivo de texto processado com UTF-8[/green]")
                except UnicodeDecodeError:
                    # Se falhar com UTF-8, tenta outras codificações
                    encodings = ['latin-1', 'cp1252', 'iso-8859-1']
                    for encoding in encodings:
                        try:
                            with open(filepath, 'r', encoding=encoding) as f:
                                content = f.read()
                            console.print(f"[green]✓ Arquivo lido com codificação {encoding}[/green]")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        console.print("[bold red]✘ Não foi possível decodificar o arquivo com nenhuma codificação conhecida[/bold red]")
                        return None
            else:
                console.print(f"[bold red]✘ Formato de arquivo não suportado:[/bold red] {file_ext}")
                console.print("[blue]Formatos suportados: .docx, .txt, .md[/blue]")
                return None
                
            # Verifica se o conteúdo está vazio
            if not content.strip():
                console.print("[bold red]✘ Arquivo vazio ou não foi possível extrair o conteúdo[/bold red]")
                return None
                
            word_count = len(content.split())
            console.print(f"[green]✓ Texto extraído com sucesso:[/green] {word_count} palavras")
            self.log_message(f"Texto extraído com sucesso: {word_count} palavras")
            return content
                
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao extrair texto do documento:[/bold red] {str(e)}")
            self.log_message(f"Erro ao extrair texto: {str(e)}", "ERROR")
            return None
            
    def _extract_document_info(self, filepath, document_text, title=None, author=None):
        """Extrai ou completa informações do documento"""
        info = {
            'title': title or self.config['ebook'].get('title', 'Ebook'),
            'author': author or self.config['ebook'].get('author', ''),
            'language': self.config['ebook'].get('language', 'pt-BR'),
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Se o título não foi fornecido, tenta extrair do documento
        if not title:
            # Tenta extrair o título da primeira linha ou do nome do arquivo
            first_line = document_text.split('\n', 1)[0].strip()
            if first_line and len(first_line) < 100:  # Verifica se a primeira linha parece um título
                info['title'] = first_line
            else:
                # Usa o nome do arquivo como título
                file_name = os.path.basename(filepath)
                base_name = os.path.splitext(file_name)[0]
                info['title'] = base_name.replace('_', ' ').title()
        
        console.print(f"[blue]ℹ Informações do documento:[/blue]")
        console.print(f"  Título: {info['title']}")
        console.print(f"  Autor: {info['author'] or '(não definido)'}")
        
        return info
    
    def _format_document_with_ai(self, document_text, document_info, headings_pattern=None):
        """Formata o documento usando IA"""
        console.print("[cyan]ℹ Formatando documento com IA...[/cyan]")
        
        # Verifica o tamanho do documento
        word_count = len(document_text.split())
        console.print(f"[blue]ℹ Documento com aproximadamente {word_count} palavras[/blue]")
        
        # Para documentos muito grandes, dividimos em chunks
        max_chunk_size = 4000  # REDUZIDO: aproximadamente palavras por chunk (ajustado para o modelo)
        
        if word_count > max_chunk_size:
            console.print(f"[yellow]⚠ Documento grande ({word_count} palavras), será processado em partes[/yellow]")
            return self._process_large_document(document_text, document_info, headings_pattern, max_chunk_size)
        else:
            # Documentos menores são processados de uma vez
            return self._format_content_chunk(document_text, document_info, headings_pattern)
    
    def _process_large_document(self, document_text, document_info, headings_pattern, max_chunk_size):
        """Processa um documento grande dividindo-o em partes"""
        # Verifica se documento está dividido em parágrafos
        if '\n\n' in document_text:
            # Dividir por parágrafos preserva melhor a estrutura
            paragraphs = document_text.split('\n\n')
        else:
            # Se não houver paragrafação clara, divide por linhas
            paragraphs = document_text.split('\n')
            # Reagrupa linhas pequenas para formar "parágrafos"
            new_paragraphs = []
            current_paragraph = []
            for line in paragraphs:
                if len(line.strip()) < 3:  # linha vazia ou quase vazia
                    if current_paragraph:
                        new_paragraphs.append('\n'.join(current_paragraph))
                        current_paragraph = []
                else:
                    current_paragraph.append(line)
            if current_paragraph:
                new_paragraphs.append('\n'.join(current_paragraph))
            paragraphs = new_paragraphs
        
        # Tenta identificar possíveis títulos/cabeçalhos para melhor divisão
        if headings_pattern:
            pattern = re.compile(headings_pattern)
        else:
            # Padrões comuns de títulos
            patterns = [
                r'^(?:Capítulo|CAPÍTULO)\s+\d+',  # Capítulo 1, CAPÍTULO 2, etc.
                r'^(?:Parte|PARTE)\s+\d+',  # Parte 1, PARTE 2, etc.
                r'^\d+\.\s+[A-Z]',  # 1. TÍTULO, 2. CONCEITOS, etc.
                r'^[IVX]+\.\s+',  # I. Título, IV. Conceitos, etc.
            ]
            pattern = re.compile('|'.join(f"({p})" for p in patterns))
        
        # NOVO: Calcula número mínimo de chunks e tamanho aproximado
        total_words = len(document_text.split())
        total_chunks = max(12, total_words // (max_chunk_size // 2))  # Forçar pelo menos 12 chunks
        approx_chunk_size = total_words // total_chunks
        
        console.print(f"[blue]ℹ Documento será dividido em pelo menos {total_chunks} partes (~{approx_chunk_size} palavras por parte)[/blue]")
        
        chunks = []
        current_chunk = []
        current_size = 0
        last_was_heading = False
        
        # Divide em chunks mantendo parágrafos inteiros e respeitando estrutura de títulos
        for para in paragraphs:
            para_size = len(para.split())
            
            # Verifica se é um título/cabeçalho
            is_heading = pattern.search(para) if headings_pattern else any(re.search(p, para) for p in patterns)
            
            # Se é um título e já temos conteúdo suficiente, começamos um novo chunk
            if is_heading and current_size > approx_chunk_size // 2 and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
                last_was_heading = True
            # Se estamos estourando o tamanho aproximado e não estamos logo após um título
            elif current_size + para_size > approx_chunk_size and current_chunk and not last_was_heading:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
                last_was_heading = is_heading
            else:
                current_chunk.append(para)
                current_size += para_size
                last_was_heading = is_heading
        
        # Adiciona o último chunk se houver conteúdo restante
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        console.print(f"[blue]ℹ Documento dividido em {len(chunks)} partes para processamento[/blue]")
        
        formatted_chunks = []
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Processando partes do documento...", total=len(chunks))
            
            for i, chunk in enumerate(chunks):
                # Adiciona contexto para o processamento das partes
                context = {
                    'part': i + 1,
                    'total_parts': len(chunks),
                    'is_first': i == 0,
                    'is_last': i == len(chunks) - 1
                }
                
                formatted_chunk = self._format_content_chunk(chunk, document_info, headings_pattern, context)
                
                if formatted_chunk:
                    formatted_chunks.append(formatted_chunk)
                    
                    # NOVO: Salvar cada parte formatada individualmente para diagnóstico
                    emergency_part_path = self.temp_dir / f"{document_info['title'].replace(' ', '_').lower()}_part_{i+1}.txt"
                    with open(emergency_part_path, 'w', encoding='utf-8') as f:
                        f.write(formatted_chunk)
                    console.print(f"[blue]ℹ Parte {i+1} salva em:[/blue] {emergency_part_path}")
                else:
                    console.print(f"[bold red]✘ Erro ao processar parte {i+1}[/bold red]")
                    self.log_message(f"Erro ao processar parte {i+1} do documento", "ERROR")
                    return None
                
                progress.update(task, advance=1)
                
                # Pequena pausa para não sobrecarregar a API
                if i < len(chunks) - 1:
                    time.sleep(2)
        
        # NOVO: Adicionar informações de diagnóstico 
        console.print(f"[blue]ℹ Total de partes processadas: {len(formatted_chunks)}[/blue]")
        total_words_processed = sum(len(chunk.split()) for chunk in formatted_chunks)
        console.print(f"[blue]ℹ Total de palavras processadas: {total_words_processed}[/blue]")
        
        # Combina as partes formatadas
        combined_content = '\n\n'.join(formatted_chunks)
        
        # NOVO: Salvar o conteúdo combinado antes da verificação de consistência
        combined_backup_path = self.temp_dir / f"{document_info['title'].replace(' ', '_').lower()}_combined_raw.txt"
        with open(combined_backup_path, 'w', encoding='utf-8') as f:
            f.write(combined_content)
        console.print(f"[green]✓ Backup do conteúdo combinado salvo em:[/green] {combined_backup_path}")
        
        # Se necessário, podemos fazer um passe final para garantir consistência
        if len(chunks) > 1:
            console.print("[cyan]ℹ Verificando consistência da formatação...[/cyan]")
            combined_content = self._ensure_formatting_consistency(combined_content, document_info)
            
        return combined_content
    
    def _format_content_chunk(self, content, document_info, headings_pattern=None, context=None):
        """Formata um trecho de conteúdo usando a IA"""
        # Cria o prompt para a IA
        system_prompt = self._create_formatting_system_prompt(headings_pattern, context)
        user_prompt = self._create_formatting_user_prompt(content, document_info, context)
        
        # Tenta a formatação com retry em caso de falha
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                console.print(f"[cyan]ℹ Enviando {len(content.split())} palavras para formatação com IA...[/cyan]")
                
                with self.client.messages.stream(
                    model=self.config['ai'].get('model', 'claude-3-opus-20240229'),
                    temperature=self.config['ai'].get('temperature', 0.1),
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                ) as stream:
                    formatted_content = ""
                    for text in stream.text_stream:
                        formatted_content += text
                        # Indicador de progresso usando print regular em vez de console.print
                        print(".", end="", flush=True)
                    print()  # Nova linha após terminar

                if formatted_content:
                    console.print("[green]✓ Conteúdo formatado com sucesso pela IA[/green]")
                    return formatted_content
                else:
                    raise Exception("A resposta da IA estava vazia")
                
            except Exception as e:
                retry_count += 1
                console.print(f"[yellow]⚠ Tentativa {retry_count}/{max_retries} falhou:[/yellow] {str(e)}")
                self.log_message(f"Tentativa {retry_count} de formatação falhou: {str(e)}", "WARNING")
                
                if retry_count < max_retries:
                    console.print(f"[blue]ℹ Aguardando 5 segundos antes de tentar novamente...[/blue]")
                    time.sleep(5)
                else:
                    console.print("[bold red]✘ Todas as tentativas falharam[/bold red]")
                    self.log_message("Todas as tentativas de formatação falharam", "ERROR")
                    return None
    
    def _ensure_formatting_consistency(self, content, document_info):
        """Garante a consistência da formatação em documentos processados em partes"""
        console.print("[cyan]ℹ Verificando consistência da formatação...[/cyan]")
        
        # NOVO: Salvar o conteúdo antes da verificação final
        pre_consistency_path = self.temp_dir / f"{document_info['title'].replace(' ', '_').lower()}_pre_consistency.txt"
        with open(pre_consistency_path, 'w', encoding='utf-8') as f:
            f.write(content)
        console.print(f"[blue]ℹ Conteúdo pré-verificação salvo em:[/blue] {pre_consistency_path}")
        
        system_prompt = """
Você é um especialista em formatação e padronização de documentos. Sua tarefa é garantir que a formatação
do documento a seguir seja consistente, verificando cabeçalhos, estilos e estrutura.

TAREFAS:
1. Verifique se a hierarquia de cabeçalhos é consistente (# Título, ## Seção, ### Subseção)
2. Padronize qualquer inconsistência de formatação
3. Remova quaisquer marcações ou artefatos que indiquem divisão em partes
4. NÃO altere o conteúdo - apenas corrija e unifique a formatação
5. Mantenha todas as informações originais
"""
        
        user_prompt = f"""
Este é um documento que foi processado em partes e agora precisa ter sua formatação padronizada.
O título principal do documento é "{document_info['title']}".

Por favor, verifique se:
- A hierarquia de cabeçalhos é consistente
- Não há quebras ou inconsistências visíveis entre as partes
- A formatação markdown é aplicada de maneira uniforme
- Não há referências à divisão em partes, como "Esta é a parte X de Y"
- Os espaços entre seções são consistentes

CONTEÚDO DO DOCUMENTO:
{content}

Retorne apenas o documento corrigido, sem explicações adicionais.
"""
        
        try:
            console.print("[cyan]ℹ Enviando para verificação final de consistência...[/cyan]")
            
            # Versão com streaming para evitar timeout
            with self.client.messages.stream(
                model=self.config['ai'].get('model', 'claude-3-opus-20240229'),
                temperature=0.1,  # Baixa temperatura para resultados consistentes
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            ) as stream:
                corrected_content = ""
                for text in stream.text_stream:
                    corrected_content += text
                    # Opcional: Imprimir pontos para indicar progresso
                    print(".", end="", flush=True)
                print()  # Nova linha após terminar
            
            if corrected_content:
                console.print("[green]✓ Formatação unificada com sucesso[/green]")
                
                # NOVO: Salvar o conteúdo após verificação para comparação
                post_consistency_path = self.temp_dir / f"{document_info['title'].replace(' ', '_').lower()}_post_consistency.txt"
                with open(post_consistency_path, 'w', encoding='utf-8') as f:
                    f.write(corrected_content)
                console.print(f"[blue]ℹ Conteúdo pós-verificação salvo em:[/blue] {post_consistency_path}")
                
                return corrected_content
            else:
                console.print("[yellow]⚠ Resposta vazia na verificação de consistência, mantendo versão atual[/yellow]")
                return content
            
        except Exception as e:
            console.print(f"[yellow]⚠ Erro ao verificar consistência, retornando versão original:[/yellow] {str(e)}")
            self.log_message(f"Erro ao verificar consistência: {str(e)}", "WARNING")
            return content
    
    def _create_formatting_system_prompt(self, headings_pattern=None, context=None):
        """Cria um prompt de sistema para formatação baseado na configuração"""
        # Adiciona informações sobre o contexto de processamento em partes
        part_info = ""
        if context:
            part_info = f"""
Este documento está sendo processado em partes. Esta é a parte {context['part']} de {context['total_parts']}.
{'Esta é a primeira parte do documento.' if context['is_first'] else ''}
{'Esta é a última parte do documento.' if context['is_last'] else ''}

Ao formatar esta parte, considere sua posição no documento completo:
- {'Na primeira parte, crie cabeçalhos de nível superior apropriados.' if context['is_first'] else 'Nas partes intermediárias, continue a estrutura de cabeçalhos da parte anterior.'}
- {'Na última parte, certifique-se de concluir apropriadamente o documento.' if context['is_last'] else ''}
"""

        # Adiciona informações sobre o padrão de cabeçalhos, se fornecido
        headings_info = ""
        if headings_pattern:
            headings_info = f"""
Foi fornecido o seguinte padrão para identificar títulos de seções: "{headings_pattern}".
Use este padrão para detectar cabeçalhos e convertê-los para a formatação Markdown adequada.
"""

        return f"""
Você é um especialista em formatação visual de ebooks. Sua tarefa é EXCLUSIVAMENTE melhorar 
a formatação visual de um documento, transformando-o em um ebook bem formatado em Markdown,
sem alterar absolutamente nada do conteúdo original.

REGRAS CRÍTICAS E ABSOLUTAS:
1. NÃO altere NENHUMA palavra do conteúdo original
2. NÃO remova NENHUMA informação, por mais detalhada ou técnica que seja
3. NÃO simplifique, resuma ou condense NADA
4. NÃO adicione conteúdo novo além de formatação Markdown
5. Preserve TODOS os exemplos de código, prompts e detalhes técnicos EXATAMENTE como estão
6. Preserve TODAS as listas, tabelas e estruturas, apenas melhorando sua formatação visual

{part_info}
{headings_info}

FOQUE EXCLUSIVAMENTE EM:
- Converter texto para formatação Markdown correta
- Estruturar cabeçalhos adequadamente (# para título principal, ## para seções, ### para subseções)
- Formatar tabelas para melhor legibilidade
- Formatar listas numeradas e com marcadores
- Destacar termos importantes com **negrito** ou *itálico*
- Formatar blocos de código com ```
- Criar espaçamento consistente entre seções

A extensão e complexidade do material são características deliberadas e importantes.
O resultado final deve ter exatamente o mesmo conteúdo, apenas apresentado de forma mais legível.
"""
    
    def _create_formatting_user_prompt(self, content, document_info, context=None):
        """Cria um prompt de usuário para formatação"""
        # Adiciona informações contextuais se o documento estiver sendo processado em partes
        context_info = ""
        if context:
            context_info = f"Esta é a parte {context['part']} de {context['total_parts']} do documento completo."
            
        return f"""
Por favor, aplique formatação Markdown adequada ao seguinte documento, PRESERVANDO 100% DO CONTEÚDO ORIGINAL.

TÍTULO DO DOCUMENTO: {document_info['title']}
{context_info}

CONTEÚDO:
{content}

INSTRUÇÕES ESPECIAIS:
1. NÃO altere NENHUMA palavra do conteúdo
2. NÃO remova NADA, mesmo que pareça redundante ou muito detalhado
3. NÃO adicione conteúdo novo, apenas formatação Markdown
4. Preserve TODOS os exemplos e detalhes técnicos

Sua tarefa é EXCLUSIVAMENTE melhorar a apresentação visual usando Markdown, mantendo 
absolutamente todo o conteúdo original intacto.
"""
    
    def _save_formatted_markdown(self, formatted_text, document_info):
        """Salva o documento formatado em Markdown"""
        console.print("[cyan]ℹ Salvando documento formatado em Markdown...[/cyan]")
        
        # Cria diretório para arquivos temporários
        self.temp_dir.mkdir(exist_ok=True)
        
        # Sanitiza o título para uso em nome de arquivo
        sanitized_title = re.sub(r'[^\w\s-]', '', document_info['title']).replace(' ', '_').lower()
        markdown_filename = f"{sanitized_title}_formatted.md"
        markdown_filepath = self.temp_dir / markdown_filename
        
        try:
            # Versão segura que não depende de frontmatter.Post
            # Constrói manualmente o frontmatter YAML
            yaml_header = "---\n"
            yaml_header += f"title: \"{document_info['title']}\"\n"
            yaml_header += f"author: \"{document_info['author']}\"\n"
            yaml_header += f"language: \"{document_info['language']}\"\n"
            yaml_header += f"date: \"{document_info['date']}\"\n"
            yaml_header += "---\n\n"
                
            # Salva o arquivo com frontmatter manual
            with open(markdown_filepath, 'w', encoding='utf-8') as f:
                f.write(yaml_header + formatted_text)
                
            console.print(f"[green]✓ Documento formatado salvo:[/green] {markdown_filepath}")
            
            # Salva backup do conteúdo formatado (para não perder o trabalho)
            backup_path = self.temp_dir / f"{sanitized_title}_formatted_backup.txt"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(formatted_text)
            console.print(f"[blue]ℹ Backup do conteúdo salvo em:[/blue] {backup_path}")
            
            # Salva uma cópia na pasta de conteúdo formatado
            formatted_dir_path = self.content_dir / "formatted" / markdown_filename
            with open(formatted_dir_path, 'w', encoding='utf-8') as f:
                f.write(yaml_header + formatted_text)
            console.print(f"[blue]ℹ Cópia salva em:[/blue] {formatted_dir_path}")
            
            return markdown_filepath
            
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao salvar documento formatado:[/bold red] {str(e)}")
            self.log_message(f"Erro ao salvar documento formatado: {str(e)}", "ERROR")
            
            # Tenta salvar pelo menos o conteúdo formatado
            try:
                emergency_path = self.temp_dir / f"{sanitized_title}_formatted_emergency.txt"
                with open(emergency_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_text)
                console.print(f"[yellow]⚠ Salvo conteúdo de emergência em:[/yellow] {emergency_path}")
            except:
                pass
                
            return None
    
    def _generate_ebook(self, markdown_filepath, output_filepath, output_format, document_info):
        """Gera o ebook no formato solicitado"""
        console.print(f"[cyan]ℹ Gerando ebook em formato {output_format}...[/cyan]")
        
        # Verifica se o diretório de saída existe
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        
        if not PYPANDOC_AVAILABLE:
            console.print("[bold yellow]⚠ pypandoc não está instalado.[/bold yellow]")
            console.print("[blue]ℹ Instale com: pip install pypandoc[/blue]")
            console.print("[blue]ℹ Você também precisa ter o Pandoc instalado: https://pandoc.org/installing.html[/blue]")
            return False
            
        try:
            # Verifica se o Pandoc está instalado
            try:
                pypandoc.get_pandoc_version()
            except:
                console.print("[bold red]✘ Pandoc não encontrado. Por favor, instale-o primeiro.[/bold red]")
                console.print("[blue]ℹ Instruções: https://pandoc.org/installing.html[/blue]")
                return False
                
            # Gera o arquivo no formato solicitado
            if output_format == 'epub':
                return self._generate_epub(markdown_filepath, output_filepath, document_info)
            elif output_format == 'pdf':
                return self._generate_pdf(markdown_filepath, output_filepath, document_info)
            elif output_format == 'html':
                return self._generate_html(markdown_filepath, output_filepath, document_info)
            else:
                console.print(f"[bold red]✘ Formato não suportado: {output_format}[/bold red]")
                return False
                
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao gerar ebook:[/bold red] {str(e)}")
            self.log_message(f"Erro ao gerar ebook: {str(e)}", "ERROR")
            return False
    
    def _generate_epub(self, markdown_filepath, output_filepath, document_info):
        """Gera ebook em formato EPUB"""
        # Verifica o arquivo de capa
        cover_image = self.config.get('ebook', {}).get('cover_image', '')
        cover_args = []
        
        if cover_image:
            cover_path = self.base_dir / cover_image
            if os.path.exists(cover_path):
                cover_args = [f'--epub-cover-image={cover_path}']
            else:
                console.print(f"[yellow]⚠ Arquivo de capa não encontrado: {cover_path}[/yellow]")
        
        # Cria arquivo CSS para o EPUB
        css_file = self.styles_dir / "epub.css"
        
        if not os.path.exists(css_file):
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(self._get_default_epub_css())
        
        # Opções para o Pandoc
        options = [
            '--toc',
            '--toc-depth=3',
            f'--css={css_file}',
            f'--metadata=title:{document_info["title"]}',
            f'--metadata=author:{document_info["author"] or "Autor"}',
            f'--metadata=lang:{document_info["language"]}'
        ] + cover_args
        
        # Executa Pandoc para conversão
        console.print("[cyan]ℹ Executando Pandoc para converter para EPUB...[/cyan]")
        
        try:
            pypandoc.convert_file(
                str(markdown_filepath),
                'epub',
                outputfile=str(output_filepath),
                extra_args=options
            )
            
            console.print(f"[green]✓ EPUB gerado com sucesso:[/green] {output_filepath}")
            return True
        except Exception as e:
            console.print(f"[bold red]✘ Erro ao gerar EPUB:[/bold red] {str(e)}")
            self.log_message(f"Erro ao gerar EPUB: {str(e)}", "ERROR")
            return False
    
    def _generate_pdf(self, markdown_filepath, output_filepath, document_info):
        """Gera ebook em formato PDF"""
        # Cria arquivo CSS para o PDF
        css_file = self.styles_dir / "pdf.css"
        
        if not os.path.exists(css_file):
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(self._get_default_pdf_css())
        
        # Tenta encontrar o wkhtmltopdf no sistema
        wkhtmltopdf_path = None
        possible_paths = [
            'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe',
            'C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe',
            '/usr/bin/wkhtmltopdf',
            '/usr/local/bin/wkhtmltopdf'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                wkhtmltopdf_path = path
                console.print(f"[green]✓ wkhtmltopdf encontrado em: {wkhtmltopdf_path}[/green]")
                break
        
        # Opções para o Pandoc
        options = [
            '--toc',
            '--toc-depth=3',
        ]
        
        # Adiciona o caminho do wkhtmltopdf se encontrado
        if wkhtmltopdf_path:
            options.append(f'--pdf-engine={wkhtmltopdf_path}')
        else:
            options.append('--pdf-engine=wkhtmltopdf')  # tenta usar do PATH
        
        # Adiciona as outras opções
        options.extend([
            f'--css={css_file}',
            f'--metadata=title:{document_info["title"]}',
            f'--metadata=author:{document_info["author"] or "Autor"}',
            f'--metadata=lang:{document_info["language"]}'
        ])
        
        # Executa Pandoc para conversão
        console.print("[cyan]ℹ Executando Pandoc para converter para PDF...[/cyan]")
        
        try:
            pypandoc.convert_file(
                str(markdown_filepath),
                'pdf',
                outputfile=str(output_filepath),
                extra_args=options
            )
            
            console.print(f"[green]✓ PDF gerado com sucesso:[/green] {output_filepath}")
            return True
        except Exception as e:
            console.print(f"[bold red]✘ Erro na geração do PDF:[/bold red] {str(e)}")
            self.log_message(f"Erro na geração do PDF: {str(e)}", "ERROR")
            
            # Sugestão alternativa se wkhtmltopdf falhar
            console.print("[yellow]⚠ Sugestão: Se o erro for com wkhtmltopdf, tente instalar:[/yellow]")
            console.print("[blue]ℹ Windows: https://wkhtmltopdf.org/downloads.html[/blue]")
            console.print("[blue]ℹ Linux: sudo apt-get install wkhtmltopdf[/blue]")
            console.print("[blue]ℹ Mac: brew install wkhtmltopdf[/blue]")
            
            # Tenta alternativa com weasyprint se disponível
            try:
                console.print("[cyan]ℹ Tentando alternativa com weasyprint...[/cyan]")
                alt_options = options.copy()
                # Substitui o engine de PDF
                for i, opt in enumerate(alt_options):
                    if opt.startswith('--pdf-engine='):
                        alt_options[i] = '--pdf-engine=weasyprint'
                        break
                else:
                    alt_options.append('--pdf-engine=weasyprint')
                
                pypandoc.convert_file(
                    str(markdown_filepath),
                    'pdf',
                    outputfile=str(output_filepath),
                    extra_args=alt_options
                )
                
                console.print(f"[green]✓ PDF gerado com sucesso usando weasyprint:[/green] {output_filepath}")
                return True
            except Exception as alt_e:
                console.print(f"[bold red]✘ Alternativa também falhou:[/bold red] {str(alt_e)}")
                return False
    
    def _generate_html(self, markdown_filepath, output_filepath, document_info):
        """Gera ebook em formato HTML"""
        # Cria arquivo CSS para o HTML
        css_file = self.styles_dir / "html.css"
        
        if not os.path.exists(css_file):
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write(self._get_default_html_css())
        
        # Verifica se o template existe, senão cria um padrão
        template_file = self.templates_dir / "html.template"
        
        if not os.path.exists(template_file):
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(self._get_default_html_template())
        
        # Opções para o Pandoc
        options = [
            '--toc',
            '--toc-depth=3',
            '--self-contained',
            f'--template={template_file}',
            f'--css={css_file}',
            f'--metadata=title:{document_info["title"]}',
            f'--metadata=author:{document_info["author"] or "Autor"}',
            f'--metadata=lang:{document_info["language"]}'
        ]
        
        # Executa Pandoc para conversão
        console.print("[cyan]ℹ Executando Pandoc para converter para HTML...[/cyan]")
        
        try:
            pypandoc.convert_file(
                str(markdown_filepath),
                'html',
                outputfile=str(output_filepath),
                extra_args=options
            )
            
            console.print(f"[green]✓ HTML gerado com sucesso:[/green] {output_filepath}")
            return True
        except Exception as e:
            console.print(f"[bold red]✘ Erro na geração do HTML:[/bold red] {str(e)}")
            self.log_message(f"Erro na geração do HTML: {str(e)}", "ERROR")
            
            # Tenta uma versão mais simples sem template personalizado
            try:
                console.print("[cyan]ℹ Tentando conversão simplificada para HTML...[/cyan]")
                simple_options = [
                    '--toc',
                    '--standalone',
                    '--self-contained',
                    f'--metadata=title:{document_info["title"]}',
                ]
                
                pypandoc.convert_file(
                    str(markdown_filepath),
                    'html',
                    outputfile=str(output_filepath),
                    extra_args=simple_options
                )
                
                console.print(f"[green]✓ HTML simplificado gerado com sucesso:[/green] {output_filepath}")
                return True
            except Exception as alt_e:
                console.print(f"[bold red]✘ Alternativa também falhou:[/bold red] {str(alt_e)}")
                return False
        
    def _get_default_epub_css(self):
        """Retorna um CSS padrão para o formato EPUB"""
        return """
body {
    font-family: serif;
    font-size: 1em;
    line-height: 1.5;
    margin: 0;
    padding: 0 1em;
    color: #333333;
}

h1, h2, h3, h4, h5, h6 {
    font-family: sans-serif;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    line-height: 1.2;
}

h1 {
    font-size: 2em;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.5em;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.3em;
}

h3 {
    font-size: 1.3em;
}

p {
    margin: 1em 0;
}

code {
    font-family: monospace;
    background-color: #f8f8f8;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
}

pre {
    background-color: #f8f8f8;
    padding: 1em;
    overflow-x: auto;
    border-radius: 5px;
    line-height: 1.45;
    margin: 1em 0;
}

pre code {
    background-color: transparent;
    padding: 0;
}

blockquote {
    border-left: 4px solid #ddd;
    margin: 1em 0;
    padding: 0 1em;
    color: #555;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}

table, th, td {
    border: 1px solid #ddd;
}

th, td {
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f8f8f8;
}

a {
    color: #0366d6;
    text-decoration: none;
}

ul, ol {
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

img {
    max-width: 100%;
    height: auto;
}
"""
    
    def _get_default_pdf_css(self):
        """Retorna um CSS padrão para o formato PDF"""
        return """
@page {
    margin: 2.5cm 2cm;
}

body {
    font-family: serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333333;
}

h1, h2, h3, h4, h5, h6 {
    font-family: sans-serif;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    line-height: 1.2;
    page-break-after: avoid;
}

h1 {
    font-size: 18pt;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.3em;
    page-break-before: always;
}

h2 {
    font-size: 16pt;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.3em;
    page-break-after: avoid;
}

h3 {
    font-size: 14pt;
    page-break-after: avoid;
}

p {
    margin: 1em 0;
    text-align: justify;
}

code {
    font-family: monospace;
    background-color: #f8f8f8;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
}

pre {
    background-color: #f8f8f8;
    padding: 1em;
    overflow-x: auto;
    border-radius: 5px;
    line-height: 1.45;
    margin: 1em 0;
    white-space: pre-wrap;
}

pre code {
    background-color: transparent;
    padding: 0;
}

blockquote {
    border-left: 4px solid #ddd;
    margin: 1em 0;
    padding: 0 1em;
    color: #555;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    page-break-inside: avoid;
}

table, th, td {
    border: 1px solid #ddd;
}

th, td {
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f8f8f8;
}

a {
    color: #0366d6;
    text-decoration: none;
}

ul, ol {
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

img {
    max-width: 100%;
    height: auto;
}

.title {
    font-size: 24pt;
    font-weight: bold;
    text-align: center;
    margin-top: 3cm;
    margin-bottom: 1cm;
}

.subtitle {
    font-size: 18pt;
    text-align: center;
    margin-bottom: 3cm;
}

.author {
    font-size: 14pt;
    text-align: center;
    margin-bottom: 5cm;
}

.date {
    font-size: 12pt;
    text-align: center;
}
"""
    
    def _get_default_html_css(self):
        """Retorna um CSS padrão para o formato HTML"""
        return """
:root {
    --primary-color: #3A86FF;
    --secondary-color: #FF006E;
    --text-color: #333333;
    --background-color: #ffffff;
    --code-bg: #f8f8f8;
    --border-color: #eee;
    --toc-bg: #f5f5f5;
}

body {
    font-family: 'Merriweather', serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-color);
    background-color: var(--background-color);
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Montserrat', sans-serif;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    line-height: 1.2;
    color: var(--primary-color);
}

h1 {
    font-size: 2.2em;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.8em;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0.2em;
}

h3 {
    font-size: 1.5em;
}

h4 {
    font-size: 1.3em;
}

p {
    margin: 1em 0;
}

code {
    font-family: 'Source Code Pro', monospace;
    background-color: var(--code-bg);
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
}

pre {
    background-color: var(--code-bg);
    padding: 1em;
    overflow-x: auto;
    border-radius: 5px;
    line-height: 1.45;
    margin: 1em 0;
}

pre code {
    background-color: transparent;
    padding: 0;
}

blockquote {
    border-left: 4px solid var(--secondary-color);
    margin: 1em 0;
    padding: 0 1em;
    color: #555;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}

table, th, td {
    border: 1px solid #ddd;
}

th, td {
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: var(--code-bg);
}

a {
    color: var(--primary-color);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

ul, ol {
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

#TOC {
    background-color: var(--toc-bg);
    padding: 20px;
    border-radius: 5px;
    margin: 20px 0;
}

#TOC ul {
    list-style-type: none;
    padding-left: 1em;
}

#TOC a {
    text-decoration: none;
}

.title {
    font-size: 2.5em;
    font-weight: bold;
    text-align: center;
    margin-top: 1em;
    margin-bottom: 0.3em;
    color: var(--primary-color);
}

.subtitle {
    font-size: 1.5em;
    text-align: center;
    margin-bottom: 1em;
    color: var(--secondary-color);
}

.author {
    font-size: 1.2em;
    text-align: center;
    margin-bottom: 2em;
}

.date {
    font-size: 1em;
    text-align: center;
    margin-bottom: 3em;
    color: #666;
}

@media (max-width: 700px) {
    body {
        padding: 10px;
        font-size: 14px;
    }
    
    h1 {
        font-size: 1.8em;
    }
    
    h2 {
        font-size: 1.5em;
    }
    
    h3 {
        font-size: 1.3em;
    }
}
"""
    
    def _get_default_html_template(self):
        """Retorna um template HTML padrão para Pandoc"""
        return """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="$lang$" xml:lang="$lang$"$if(dir)$ dir="$dir$"$endif$>
<head>
  <meta charset="utf-8" />
  <meta name="generator" content="pandoc" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />
$for(author-meta)$
  <meta name="author" content="$author-meta$" />
$endfor$
$if(date-meta)$
  <meta name="dcterms.date" content="$date-meta$" />
$endif$
$if(keywords)$
  <meta name="keywords" content="$for(keywords)$$keywords$$sep$, $endfor$" />
$endif$
  <title>$if(title-prefix)$$title-prefix$ – $endif$$pagetitle$</title>
  <style>
    $styles.html()$
  </style>
$for(css)$
  <link rel="stylesheet" href="$css$" />
$endfor$
$if(math)$
  $math$
$endif$
</head>
<body>
$for(include-before)$
$include-before$
$endfor$
$if(title)$
<header id="title-block-header">
<h1 class="title">$title$</h1>
$if(subtitle)$
<p class="subtitle">$subtitle$</p>
$endif$
$for(author)$
<p class="author">$author$</p>
$endfor$
$if(date)$
<p class="date">$date$</p>
$endif$
</header>
$endif$
$if(toc)$
<nav id="$idprefix$TOC" role="doc-toc">
$if(toc-title)$
<h2 id="$idprefix$toc-title">$toc-title$</h2>
$endif$
$table-of-contents$
</nav>
$endif$
$body$
$for(include-after)$
$include-after$
$endfor$
</body>
</html>
"""