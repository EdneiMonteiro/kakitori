# Nihongo Kakitori - Japanese Learning App

Uma aplicação web para aprendizado de japonês convertida de C# Console para Python Flask com frontend HTML.

## 🚀 Funcionalidades

- **Adicionar Palavras**: Busca automática de significados no Jisho.org
- **Geração de Áudio**: Síntese de voz usando Azure Speech Services
- **Prática Interativa**: Sistema de kakitori (ditado) com diferentes vozes
- **Acompanhamento de Progresso**: Sistema de sessões e pontuação
- **Tradução Automática**: Integração com Azure Translator

## 📋 Pré-requisitos

- Python 3.8+
- Conta Azure (para Speech Services e Translator)
- SQLite (incluído no Python)

## 🛠️ Instalação

1. **Clone ou baixe os arquivos do projeto**

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure as variáveis de ambiente:**
   
   a) Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```
   
   b) Edite o arquivo `.env` com suas credenciais do Azure:
   ```bash
   # Azure Speech Services
   AZURE_SPEECH_KEY=sua_chave_do_speech_service_aqui
   AZURE_SPEECH_REGION=eastus2

   # Azure Translator (opcional)
   AZURE_TRANSLATOR_KEY=sua_chave_do_translator_aqui
   AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
   AZURE_TRANSLATOR_REGION=eastus2
   ```

4. **Crie a estrutura de diretórios:**
   ```
   projeto/
   ├── app.py
   ├── requirements.txt
   ├── .env                    # Suas credenciais (não committar)
   ├── .env.example           # Template das variáveis
   ├── .gitignore
   ├── templates/
   │   ├── base.html
   │   ├── index.html
   │   ├── add_word.html
   │   └── practice.html
   └── kakitori.db (será criado automaticamente)
   ```

## ▶️ Execução

1. **Inicie a aplicação:**
   ```bash
   python app.py
   ```

2. **Acesse no navegador:**
   ```
   http://localhost:5000
   ```

## 🎯 Como Usar

### Adicionar Palavras
1. Vá para "Adicionar Palavra"
2. Digite uma palavra em japonês (hiragana, katakana ou kanji)
3. Selecione o significado correto da lista
4. Escolha se deseja usar kanji para áudio
5. Opcionalmente, customize a tradução
6. Salve a palavra

### Praticar
1. Vá para "Praticar"
2. Configure a sessão:
   - Use sessão específica (opcional)
   - Defina quantidade de palavras
   - Ajuste intervalo entre áudios
3. Ouça os áudios e tente identificar a palavra
4. Marque se acertou a palavra e tradução
5. Veja sua pontuação final

## 🔒 Segurança

- **NUNCA committe o arquivo `.env`** - ele contém suas credenciais privadas
- O arquivo `.gitignore` já está configurado para ignorar o `.env`
- Use o arquivo `.env.example` como template para outros desenvolvedores
- Mantenha suas chaves do Azure seguras e rotate-as periodicamente

## 🔧 Configuração do Azure

### Azure Speech Services
1. Crie um recurso "Speech Services" no portal Azure
2. Copie a chave e região
3. Cole no `app.py`

### Azure Translator (opcional)
1. Crie um recurso "Translator" no portal Azure
2. Copie a chave, endpoint e região
3. Cole no `app.py`

## 📊 Estrutura do Banco de Dados

- **hiragana**: Palavras cadastradas com áudios
- **sessions**: Sessões de prática
- **session_words**: Palavras de cada sessão
- **session_attempts**: Tentativas e resultados

## 🎨 Recursos Visuais

- Interface moderna com gradientes e efeitos
- Design responsivo para mobile
- Animações suaves
- Feedback visual para interações

## 🔊 Recursos de Áudio

- 3 vozes japonesas diferentes (Naoki, Nanami, Aoi)
- Reprodução automática durante prática
- Controles manuais de áudio
- Suporte a kanji e hiragana/katakana

## 📝 Notas Importantes

- As credenciais do Azure são necessárias para funcionalidade completa
- Sem credenciais, o app funcionará mas sem áudio e tradução
- O banco SQLite é criado automaticamente na primeira execução
- Os áudios são armazenados como BLOB no banco de dados

## 🐛 Troubleshooting

### Erro de áudio
- Verifique as credenciais do Azure Speech
- Confirme se a região está correta

### Erro de tradução
- Verifique as credenciais do Azure Translator
- A tradução é opcional, o app funciona sem ela

### Erro de scraping
- O Jisho.org pode bloquear muitas requisições
- Aguarde alguns minutos entre buscas intensivas

## 🚀 Melhorias Futuras

- [ ] Cache de resultados do Jisho.org
- [ ] Exportação/importação de palavras
- [ ] Sistema de níveis JLPT
- [ ] Estatísticas detalhadas
- [ ] Modo offline
- [ ] API REST completa

## 📄 Licença

Este projeto é uma conversão do sistema original em C# e mantém a mesma funcionalidade com melhorias na interface web.