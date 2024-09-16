from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
import ollama
import json
import os
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from bs4 import BeautifulSoup
import requests
import logging
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import nltk
import psutil
from queue import Queue
from threading import Thread


app = Flask(__name__)

nltk.download('punkt')
nltk.download('stopwords')

Base = declarative_base()

class Memoria(Base):
    __tablename__ = 'memoria'
    id = Column(String, primary_key=True)
    transcricao_completa = Column(JSON)
    preferencias = Column(JSON)

class AssistenteAI:
    def __init__(self, db_url='sqlite:///memoria_usuario.db'):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        self.transcricao_completa = [
            {"role": "system", "content": "Você é um modelo de linguagem chamado Jarvis criado por Panubiin. Responda às perguntas feitas com quantos caracteres for necessário. Não use asteriscos, pois isso será passado para um serviço de texto para fala. Sempre responda em português do Brasil. Quando te pedirem para fazer alguma coisa, faça por completo!"}
        ]
        self.preferencias = []
        self.memoria_pesquisa = {}
        self.carregar_memoria()

        # Inicialização dos componentes de pesquisa web
        self.ua = UserAgent()
        self.palavras_irrelevantes = set(stopwords.words('portuguese'))
        self.sessao_web = requests.Session()
        self.sessao_web.headers.update({'User-Agent': self.ua.random})

    def verificar_recursos_e_otimizar(self):
        uso_cpu = psutil.cpu_percent(interval=1)
        uso_memoria = psutil.virtual_memory().percent
        
        print(f"Uso de CPU: {uso_cpu}%")
        print(f"Uso de Memória: {uso_memoria}%")

        if uso_cpu > 70 or uso_memoria > 80:
            print("Alerta: Recursos elevados! Ajustando desempenho.")
            return "reduzir"
        else:
            return "normal"

    # Função que realiza uma tarefa com base no nível de ajuste
    def tarefa_complexa(self, nivel_ajuste="normal"):
        if nivel_ajuste == "reduzir":
            print("Executando versão otimizada da função.")
            for _ in range(1000000):  # Versão otimizada
                pass
        else:
            print("Executando versão completa da função.")
            for _ in range(10000000):  # Versão completa
                pass

    # Função de throttle que aplica uma pausa baseada no uso de CPU
    def throttle_based_on_cpu(self):
        while True:
            uso_cpu = psutil.cpu_percent(interval=1)
            if uso_cpu > 80:
                print("Uso de CPU alto! Aplicando throttle...")
                time.sleep(2)  # Pausa para reduzir a carga no sistema
            else:
                print("CPU estável. Continuando operações.")
            # Coloque aqui o código que você deseja executar continuamente

    # Função do trabalhador para a fila de processamento
    def worker(self, q):
        while True:
            tarefa = q.get()
            if tarefa is None:
                break
            tarefa()  # Executa a tarefa
            q.task_done()

    # Configuração da fila e das threads
    def configurar_threads(self):
        q = Queue(maxsize=5)  # Limita a fila a 5 tarefas
        threads = []
        for _ in range(3):  # Três threads de trabalho
            t = Thread(target=self.worker, args=(q,))
            t.start()
            threads.append(t)
        return q, threads

    def processar_tarefas(self):
        q, threads = self.configurar_threads()

        while True:
            ajuste = self.verificar_recursos_e_otimizar()  # Verifica uso de CPU/Memória
            self.tarefa_complexa(ajuste)  # Executa a tarefa com ajuste dinâmico
            self.throttle_based_on_cpu()  # Aplica throttle baseado no uso de CPU
            
            # Adiciona tarefas à fila
            for _ in range(10):  # Se tentar adicionar mais de 5, ele irá aguardar
                q.put(lambda: print("Processando tarefa"))

            q.join()  # Espera até que todas as tarefas sejam concluídas

            # Finaliza as threads
            for t in threads:
                q.put(None)
            for t in threads:
                t.join()
            
            time.sleep(5)  # Intervalo de tempo entre verificações     

    def carregar_memoria(self):
        memoria = self.session.query(Memoria).filter_by(id='default').first()
        if memoria:
            self.transcricao_completa = memoria.transcricao_completa or self.transcricao_completa
            self.preferencias = memoria.preferencias or []
        else:
            memoria = Memoria(id='default', transcricao_completa=self.transcricao_completa, preferencias=[])
            self.session.add(memoria)
            self.session.commit()

    def salvar_memoria(self):
        memoria = self.session.query(Memoria).filter_by(id='default').first()
        if memoria:
            memoria.transcricao_completa = self.transcricao_completa
            memoria.preferencias = self.preferencias
            self.session.commit()
        else:
            memoria = Memoria(id='default', transcricao_completa=self.transcricao_completa, preferencias=self.preferencias)
            self.session.add(memoria)
            self.session.commit()

    def classificar_solicitacao(self, texto):
        palavras_chave_pesquisa = ['faça uma pesquisa', 'pesquise', 'pesquise sobre', 'pesquisa sobre']
        palavras_chave_abertura = ['abra', 'inicie', 'abrir', 'abrir site']
        
        if any(palavra in texto.lower() for palavra in palavras_chave_pesquisa):
            return 'pesquisa'
        elif any(palavra in texto.lower() for palavra in palavras_chave_abertura):
            return 'abertura'
        return 'normal'

    def processar_transcricao(self, textos):
        respostas = []
        for texto in textos:
            tipo_solicitacao = self.classificar_solicitacao(texto)
            if tipo_solicitacao == 'pesquisa':
                resposta = self.executar_pesquisa_web(texto)
            elif tipo_solicitacao == 'abertura':
                resposta = self.abrir_app_ou_site(texto)
            elif tipo_solicitacao == 'preferencia':
                resposta = self.gerar_resposta_ia(texto)
                self.detectar_preferencias(texto, resposta)
            else:
                resposta = self.gerar_resposta_ia(texto)
            respostas.append(resposta)
            self.atualizar_memoria(texto, resposta)
        return respostas

    def executar_pesquisa_web(self, texto):
        logging.info(f"Iniciando processamento para: {texto}")

        termo_pesquisa = texto.replace('pesquise', '').replace('faça uma pesquisa', '').strip()

        if termo_pesquisa in self.memoria_pesquisa:
            logging.info(f"Retornando resultados da memória para: {termo_pesquisa}")
            return self.memoria_pesquisa[termo_pesquisa]

        logging.info(f"Iniciando pesquisa na web para: {termo_pesquisa}")
        url = f'https://www.google.com/search?q={termo_pesquisa.replace(" ", "+")}'
        headers = {'User-Agent': 'Mozilla/5.0'}

        resultados = []
        try:
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    logging.error("Erro ao acessar os resultados da pesquisa.")
                    return "Erro ao acessar os resultados da pesquisa."
                
                soup = BeautifulSoup(response.text, 'html.parser')

                seletores = [
                    {'tag': 'div', 'class': 'BNeawe iBp4i AP7Wnd'},
                    {'tag': 'span', 'class': 'BNeawe s3v9rd AP7Wnd'},
                    {'tag': 'a', 'class': 'BVG0Nb'},
                    {'tag': 'div', 'class': 'kCrYT'},
                    {'tag': 'h3', 'class': 'zBAuLc'},
                    {'tag': 'div', 'class': 'BNeawe UPmit AP7Wnd'},
                    {'tag': 'div', 'class': 'BNeawe s3v9rd AP7Wnd'},
                    {'tag': 'p'}
                ]

                for seletor in seletores:
                    elementos = soup.find_all(seletor['tag'], class_=seletor.get('class'))
                    for elemento in elementos:
                        texto = elemento.get_text(strip=True)
                        if texto:
                            resultados.append(texto)

                proxima_pagina = soup.find('a', {'aria-label': 'Próxima'})
                if proxima_pagina and 'href' in proxima_pagina.attrs:
                    url = 'https://www.google.com' + proxima_pagina['href']
                    logging.info(f"Próxima URL: {url}")
                else:
                    url = None

        except requests.RequestException as e:
            logging.error(f"Erro ao acessar os resultados da pesquisa: {e}")
            return "Erro ao acessar os resultados da pesquisa."

        except Exception as e:
            logging.error(f"Erro ao processar os resultados da pesquisa: {e}")
            return "Erro ao processar os resultados da pesquisa."

        conteudo_pagina = "\n\n".join(resultados)
        self.memoria_pesquisa[termo_pesquisa] = conteudo_pagina
        self.salvar_memoria()

        return f"Resultados salvos para a pesquisa: {termo_pesquisa}\nConteúdo da página:\n{conteudo_pagina[:1500]}..."


    def gerar_resposta_ia(self, texto):
        self.transcricao_completa.append({"role": "user", "content": texto})
        ollama_stream = ollama.chat(
            model="llama3",
            messages=self.transcricao_completa,
            stream=True
        )
        
        full_text = ""
        for chunk in ollama_stream:
            full_text += chunk['message']['content']

        self.transcricao_completa.append({"role": "assistant", "content": full_text})
        return full_text

    def abrir_app_ou_site(self, texto_usuario):  
        # Definindo o prompt para ser analisado pela IA
        prompt_abrir = f"""  
        Analise o seguinte texto do usuário: "{texto_usuario}"  
        
        1. Determine se é uma mensagem normal ou uma solicitação de abrir um app.  
        2. Determine o nome do aplicativo que deve ser aberto.  
        3. Execute a abertura do aplicativo.  
        
        Responda no formato:  
        Ação: [ação]  
        """  
        
        # Certifique-se de que a variável resposta_ia está definida
        resposta_ia = self.gerar_resposta_ia(prompt_abrir)
        
        if resposta_ia:  
            # Extrai a ação da resposta da IA
            acao = resposta_ia.strip().split(': ')[1].strip()  
            
            # Verifique se a ação é abrir um aplicativo  
            if acao.lower().startswith('abrir'):  
                app_name = acao.split(' ')[-1]  
                os.system(f'start {app_name}')  # Comando para abrir um aplicativo no Windows  
                print(f"Aplicativo {app_name} aberto com sucesso.")  
            else:  
                print("Ação não reconhecida. Apenas aplicativos podem ser abertos.")  
        else:
            print("Nenhuma resposta foi recebida da IA.")
   

    def detectar_preferencias(self, texto, resposta):
        prompt_preferencia = f"Identifique possíveis preferências do usuário nas seguintes interações do usuário:\nUsuário: {texto}\nResposta da IA: {resposta}\nSe houver preferências, verifique se é algo impróprio ou não, se não for (o texto explicativo tem que ser curto) quais são elas? e se for não salve"
        analise_preferencia = self.gerar_resposta_ia(prompt_preferencia)
        if analise_preferencia.strip():
            self.preferencias = list(set(self.preferencias + [analise_preferencia.strip()]))
            self.salvar_memoria()

    def atualizar_memoria(self, texto, resposta):
        self.transcricao_completa.append({"role": "user", "content": texto})
        self.transcricao_completa.append({"role": "assistant", "content": resposta})
        
        if len(self.transcricao_completa) > 1000:
            self.transcricao_completa.pop(0)
        
        self.salvar_memoria()

# Instância do Assistente AI
assistente_ai = AssistenteAI()

# Rota para processar mensagens
@app.route('/get-response-stream')
def get_response_stream():
    @stream_with_context
    def generate():
        mensagens = request.args.getlist('message')
        respostas = assistente_ai.processar_transcricao(mensagens)
        
        for resposta in respostas:
            for char in resposta:
                yield f"data: {char}\n\n"
                time.sleep(0.02)  # Ajuste o delay para a animação de digitação

            yield "data: [FIM]\n\n"  # Marcação de fim de mensagem

    return Response(generate(), content_type='text/event-stream')

# Rota para servir a página HTML
@app.route('/')
def index():
    return render_template_string(html_template)

# HTML do Chat
html_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #343541;
            color: #eaeaea;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        #chat-container {
            width: 80%;
            max-width: 800px;
            margin: 0 auto;
            background: #1e1e1e;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            height: 90vh;
            overflow-y: auto;
        }
        #message-box {
            display: flex;
            margin-top: 10px;
        }
        #input-message {
            flex: 1;
            padding: 10px;
            border: 1px solid #555;
            border-radius: 4px;
            background: #222;
            color: #eaeaea;
        }
        #send-button {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            background: #007bff;
            color: #fff;
            cursor: pointer;
            margin-left: 10px;
        }
        #send-button:hover {
            background: #0056b3;
        }
        .message {
            display: flex;
            align-items: flex-start;
            margin-bottom: 10px;
            width: 100%; /* Ocupa a largura total disponível */
            justify-content: flex-start; /* Por padrão, as mensagens vão para a esquerda */
            overflow-wrap: break-word; /* Quebra o texto longo para evitar ultrapassagem */
        }
        .message.user-message {
            justify-content: flex-end; /* Alinha as mensagens do usuário à direita */
        }

        .text {
            max-width: 70%; /* Limita a largura das mensagens */
            word-wrap: break-word; /* Garante a quebra de palavras longas */
            background-color: #515154;
            padding: 10px;
            border-radius: 10px;
            overflow-wrap: break-word; /* Quebra o texto longo */
            word-break: break-word; /* Quebra as palavras longas se necessário */
        }
        .code-block {
           max-width: 70%; /* Limita a largura das mensagens de código */
           background-color: #2d2d2d;
           color: #515154;
           padding: 10px;
           border-radius: 8px;
           overflow: auto; /* Adiciona barras de rolagem se o código for muito largo */
           word-wrap: break-word; /* Garante que o código longo será quebrado */
           white-space: pre-wrap; /* Mantém o formato do código e quebra linhas */
       }
        .logo {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
            margin-right: 10px;
        }
        .user-message .logo {
            display: none; /* Esconde a imagem para mensagens do usuário */
        }
        .assistant-message .text {
            background-color: #515154; /* Cor de fundo diferente para mensagens da IA */
        }
        .typing-indicator {
            display: inline-block;
            width: 100px;
            height: 20px;
            background: #333;
            color: #fff;
            text-align: center;
            line-height: 20px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div id="chat-container">
        <div id="messages"></div>
        <div id="message-box">
            <input id="input-message" type="text" placeholder="Digite sua mensagem..." />
            <button id="send-button">Enviar</button>
        </div>
    </div>
    <script>
        const messagesDiv = document.getElementById('messages');
        const inputMessage = document.getElementById('input-message');
        const sendButton = document.getElementById('send-button');

        function appendMessage(text, role) {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message');
            messageDiv.classList.add(`${role}-message`);
            
            if (role === 'assistant') {
                const logo = document.createElement('img');
                logo.classList.add('logo');
                logo.src = 'https://i.ibb.co/hRbh58Y/logo-1-1.png';
                logo.alt = 'AI Logo';
                messageDiv.appendChild(logo);
            }

            const textDiv = document.createElement('div');
            textDiv.classList.add('text');
            textDiv.innerHTML = formatText(text);

            messageDiv.appendChild(textDiv);
            
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function handleStream() {
            const eventSource = new EventSource('/get-response-stream?message=' + encodeURIComponent(inputMessage.value));
            let buffer = '';
            let typingIndicator = document.createElement('div');
            typingIndicator.classList.add('typing-indicator');
            typingIndicator.textContent = 'Digitando...';
            messagesDiv.appendChild(typingIndicator);

            eventSource.onmessage = function(event) {
                if (event.data === '[FIM]') {
                    appendMessage(buffer, 'assistant');
                    typingIndicator.remove();
                    eventSource.close();
                    return;
                }

                buffer += event.data;
                typingIndicator.textContent = buffer;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            };

            eventSource.onerror = function() {
                typingIndicator.remove();
                eventSource.close();
            };
        }

        sendButton.addEventListener('click', () => {
            const message = inputMessage.value;
            if (message.trim()) {
                appendMessage(message, 'user');
                handleStream();
                inputMessage.value = '';
            }
        });

        function formatText(text) {
            const codeRegex = /(```[\s\S]*?```)/g;
            const boldRegex = /\*(.*?)\*/g;
            let formattedText = '';
            let lastIndex = 0;
            let match;

            while ((match = codeRegex.exec(text)) !== null) {
                formattedText += escapeHTML(text.substring(lastIndex, match.index));
                formattedText += '<div class="code-block"><button onclick="copyToClipboard(this)">&lt;&gt;</button><pre><code>' + escapeHTML(match[1]) + '</code></pre></div>';
                lastIndex = codeRegex.lastIndex;
            }

            formattedText += escapeHTML(text.substring(lastIndex));
            formattedText = formattedText.replace(boldRegex, '<b>$1</b>');
            return formattedText;
        }

        function escapeHTML(text) {
            return text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function copyToClipboard(button) {
            const codeBlock = button.nextElementSibling.textContent;
            navigator.clipboard.writeText(codeBlock)
                .then(() => alert("Copiado!"))
                .catch(err => console.error("Erro ao copiar: ", err));
        }
    </script>
</body>
</html>

'''

if __name__ == "__main__":
    app.run(debug=True)

