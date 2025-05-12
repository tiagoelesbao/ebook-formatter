#!/usr/bin/env python3
import click
from rich.console import Console
import os
import sys
from src.simple_ebook_manager import SimpleEbookManager

console = Console()

@click.command()
@click.argument('filepath', type=click.Path(exists=True))
@click.option('--title', '-t', help='Título do ebook (se não fornecido, será extraído do documento)')
@click.option('--author', '-a', help='Autor do ebook')
@click.option('--output-format', '-f', 
              type=click.Choice(['epub', 'pdf', 'html']), 
              default='epub', 
              help='Formato de saída do ebook')
@click.option('--output-file', '-o', help='Caminho para o arquivo de saída (opcional)')
@click.option('--headings-pattern', '-p', 
              help='Padrão regex para identificar títulos de capítulos (opcional)')
def format_ebook(filepath, title, author, output_format, output_file, headings_pattern):
    """
    Converte um documento em um ebook formatado.
    
    Lê um documento DOCX, TXT ou MD, formata-o com IA e gera um ebook
    no formato especificado, preservando 100% do conteúdo original.
    
    FILEPATH: Caminho para o arquivo a ser convertido
    """
    # Verifica se a chave API está configurada
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[bold yellow]⚠ ANTHROPIC_API_KEY não está definida no ambiente[/bold yellow]")
        console.print("É necessário configurar a chave API para formatação com IA")
        api_key = console.input("[bold]Forneça sua chave API agora: [/bold]")
        os.environ["ANTHROPIC_API_KEY"] = api_key

    console.print(f"\n[bold cyan]🔍 Verificando arquivo:[/bold cyan] {filepath}")
    
    # Verifica se o arquivo existe
    if not os.path.exists(filepath):
        console.print(f"[bold red]✘ Arquivo não encontrado:[/bold red] {filepath}")
        sys.exit(1)
        
    # Criando o gerenciador de ebook simplificado
    try:
        console.print("[cyan]ℹ Inicializando gerenciador de ebook...[/cyan]")
        manager = SimpleEbookManager()
    except Exception as e:
        console.print(f"[bold red]✘ Erro ao inicializar gerenciador:[/bold red] {str(e)}")
        sys.exit(1)
    
    # Executando o processo completo
    console.print("[bold cyan]📖 Iniciando processamento do documento...[/bold cyan]")
    
    success = manager.process_document(
        filepath=filepath,
        title=title,
        author=author,
        output_format=output_format,
        output_file=output_file,
        headings_pattern=headings_pattern
    )
    
    if success:
        console.print("\n[bold green]✅ Documento processado e ebook gerado com sucesso![/bold green]")
    else:
        console.print("\n[bold red]❌ Ocorreu um erro durante o processamento.[/bold red]")
        console.print("Verifique os logs para mais detalhes.")
        sys.exit(1)

if __name__ == '__main__':
    format_ebook()