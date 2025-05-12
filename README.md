# E-book Formatter

Um sistema para conversão e formatação de documentos em e-books usando Inteligência Artificial, com foco na preservação total do conteúdo original.

## Sobre o Projeto

O E-book Formatter é uma ferramenta que utiliza a IA da Anthropic (Claude) para converter documentos DOCX, TXT ou MD em e-books bem formatados nos formatos EPUB, PDF ou HTML. A ferramenta foi desenvolvida para:

- Preservar 100% do conteúdo original
- Melhorar a formatação visual do documento
- Estruturar os títulos e seções adequadamente
- Processar documentos de qualquer tamanho automaticamente
- Gerar e-books em múltiplos formatos

## Recursos

- **Processamento Simplificado**: Converte documentos em e-books em um único comando
- **Formatação com IA**: Utiliza o Claude da Anthropic para formatação inteligente
- **Processamento de Documentos Grandes**: Divide documentos grandes automaticamente, preservando a estrutura
- **Múltiplos Formatos de Saída**: EPUB, PDF e HTML
- **Preservação de Conteúdo**: Mantém todo o conteúdo original intacto
- **Interface de Linha de Comando**: Fácil de usar em scripts ou manualmente

## Instalação

### Pré-requisitos

- Python 3.7 ou superior
- Pandoc (para conversão de formatos)
- Uma chave API da Anthropic (para acessar a IA Claude)

### Passos de Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/tiagoelesbao/ebook-formatter.git
   cd ebook-formatter
   ```

2. Crie um ambiente virtual e instale as dependências:
   ```bash
   python -m venv venv
   
   # No Windows
   venv\Scripts\activate
   
   # No Linux/Mac
   source venv/bin/activate
   
   pip install -r requirements.txt
   ```

3. Instale o Pandoc (necessário para gerar os formatos de saída):
   - **Windows**: Baixe o instalador em [pandoc.org](https://pandoc.org/installing.html)
   - **macOS**: `brew install pandoc`
   - **Linux**: `sudo apt-get install pandoc`

4. Para geração de PDF, instale o wkhtmltopdf:
   - **Windows**: Baixe em [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html)
   - **macOS**: `brew install wkhtmltopdf`
   - **Linux**: `sudo apt-get install wkhtmltopdf`

## Uso

### Modo Simplificado

Para processar um documento de forma rápida e gerar um e-book formatado:

```bash
python simple_formatter.py seu_documento.docx
```

### Opções Disponíveis

```bash
python simple_formatter.py seu_documento.docx [OPÇÕES]
```

Opções:
- `--title`, `-t`: Título do e-book
- `--author`, `-a`: Autor do e-book
- `--output-format`, `-f`: Formato de saída (epub, pdf, html)
- `--output-file`, `-o`: Caminho para o arquivo de saída
- `--headings-pattern`, `-p`: Padrão regex para identificar títulos de capítulos

### Exemplos

Converter um documento com título e autor personalizados:
```bash
python simple_formatter.py documento.docx -t "Meu E-book" -a "Autor"
```

Gerar um e-book em formato PDF:
```bash
python simple_formatter.py documento.docx -f pdf
```

Especificar um arquivo de saída:
```bash
python simple_formatter.py documento.docx -o "meu_ebook.epub"
```

## Configuração

Você pode personalizar o comportamento do formatador editando o arquivo `config.yaml`:

```yaml
ebook:
  title: "Meu E-book"
  subtitle: ""
  author: ""
  language: "pt-BR"
  cover_image: "assets/images/cover.jpg"
  
ai:
  model: "claude-3-opus-20240229"
  max_tokens: 100000
  temperature: 0.1
```

## Estrutura de Diretórios

Após a execução, o programa criará os seguintes diretórios:

- `temp/`: Arquivos temporários gerados durante o processamento
- `output/`: E-books gerados (subdivididos por formato)
- `src/styles/`: Arquivos CSS para os diferentes formatos
- `src/templates/`: Templates para conversão
- `logs/`: Arquivos de log
- `content/`: Conteúdo original e formatado

## Dicas e Solução de Problemas

- **Configuração da API**: Configure a chave API da Anthropic como uma variável de ambiente:
  ```bash
  export ANTHROPIC_API_KEY=sua_chave_api
  ```
  Ou forneça quando solicitado pelo programa.

- **Documentos Grandes**: A ferramenta divide automaticamente documentos grandes para processamento. Isso pode demorar mais tempo, mas garante que todo o conteúdo seja processado corretamente.

- **Problemas com PDF**: Se ocorrer um erro ao converter para PDF, verifique se o wkhtmltopdf está instalado corretamente.

- **Formatação**: A ferramenta preserva todo o conteúdo original, focando apenas em melhorar a estrutura e formatação visual.

## Contribuindo

Contribuições são bem-vindas! Se você encontrar um bug ou tiver sugestões de melhorias, por favor:

1. Crie um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Faça commit das suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Faça push para a branch (`git push origin feature/nova-funcionalidade`)
5. Crie um novo Pull Request

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.

## Créditos

- **Anthropic Claude**: Utilizado para a formatação inteligente do conteúdo
- **Pandoc**: Utilizado para conversão entre formatos de documentos
- **Python**: Linguagem de programação utilizada para desenvolver a ferramenta
