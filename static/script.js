document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const voiceButton = document.getElementById('voice-button');
    const voiceQuestionInput = document.getElementById('voice_question');
    const loadingIndicator = document.getElementById('loading-indicator');
    const form = document.getElementById('survey-form');
    
    // Speech Recognition Setup
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = 'ru-RU';
        recognition.interimResults = false;

        voiceButton.addEventListener('click', () => {
            recognition.start();
            voiceButton.disabled = true;
            voiceButton.textContent = 'Слушаю...';
        });

        recognition.addEventListener('result', async (event) => {
            const transcript = event.results[0][0].transcript;
            try {
                loadingIndicator.style.display = 'block';
                const response = await fetch('/process_voice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ voice_input: transcript })
                });

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                
                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }
                
                voiceQuestionInput.value = data.corrected_question;
                
            } catch (error) {
                console.error('Voice processing error:', error);
                alert('Ошибка при обработке голосового ввода: ' + error.message);
            } finally {
                loadingIndicator.style.display = 'none';
                voiceButton.disabled = false;
                voiceButton.textContent = '🎤 Голосовой ввод';
            }
        });

        recognition.addEventListener('error', (event) => {
            console.error('Speech recognition error:', event.error);
            alert('Ошибка распознавания речи: ' + event.error);
            voiceButton.disabled = false;
            voiceButton.textContent = '🎤 Голосовой ввод';
        });
    } else {
        voiceButton.disabled = true;
        voiceButton.textContent = 'Голосовой ввод не поддерживается';
    }

    // ChatGPT Modal Setup
    const setupChatGPT = () => {
        const modal = document.getElementById('chatgpt-modal');
        const chatBtn = document.getElementById('chatgpt-button');
        const closeBtn = document.querySelector('.close');
        const chatInput = document.getElementById('chatgpt-input');
        const chatSend = document.getElementById('chatgpt-send');
        const chatContainer = document.getElementById('chatgpt-chat');
        const chatgptQuestionsInput = document.getElementById('chatgpt_questions');

        let isProcessingChat = false;

        const toggleModal = (show) => {
            modal.style.display = show ? 'block' : 'none';
        };

        chatBtn.addEventListener('click', () => toggleModal(true));
        closeBtn.addEventListener('click', () => toggleModal(false));

        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                toggleModal(false);
            }
        });

        const appendMessage = (message, className) => {
            const messageDiv = document.createElement('div');
            messageDiv.className = className;
            messageDiv.textContent = message;
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        };

        const handleChatSubmit = async () => {
            if (isProcessingChat) return;

            const message = chatInput.value.trim();
            if (!message) return;

            try {
                isProcessingChat = true;
                loadingIndicator.style.display = 'block';
                chatInput.value = '';
                appendMessage(message, 'user-message');

                const response = await fetch('/chatgpt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ message })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }

                appendMessage(data.reply, 'bot-message');
                chatgptQuestionsInput.value += `User: ${message}\nChatGPT: ${data.reply}\n`;

            } catch (error) {
                console.error('ChatGPT error:', error);
                alert('Ошибка при обработке запроса: ' + error.message);
            } finally {
                isProcessingChat = false;
                loadingIndicator.style.display = 'none';
            }
        };

        chatSend.addEventListener('click', handleChatSubmit);
        chatInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleChatSubmit();
            }
        });
    };

    setupChatGPT();

    // Form Validation
    if (form) {
        form.addEventListener('submit', (event) => {
            const requiredInputs = form.querySelectorAll('[required]');
            let isValid = true;

            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.classList.add('error');
                    input.setAttribute('title', 'Это поле обязательно для заполнения');
                } else {
                    input.classList.remove('error');
                    input.removeAttribute('title');
                }
            });

            if (!isValid) {
                event.preventDefault();
                alert('Пожалуйста, заполните все обязательные поля');
            }
        });
    }
});
