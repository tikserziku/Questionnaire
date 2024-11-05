document.addEventListener('DOMContentLoaded', () => {
    // Элементы интерфейса
    const voiceButton = document.getElementById('voice-button');
    const voiceQuestionInput = document.getElementById('voice_question');
    const chatButton = document.getElementById('chatgpt-button');
    const chatModal = document.getElementById('chatgpt-modal');
    const chatInput = document.getElementById('chatgpt-input');
    const chatSend = document.getElementById('chatgpt-send');
    const chatContainer = document.getElementById('chatgpt-chat');
    const chatgptQuestionsInput = document.getElementById('chatgpt_questions');
    const loadingIndicator = document.getElementById('loading-indicator');
    const closeModalBtn = document.querySelector('.close');

    // Настройка распознавания речи
    let recognition = null;
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        recognition = new (window.webkitSpeechRecognition || window.SpeechRecognition)();
        recognition.lang = 'ru-RU';
        recognition.continuous = false;
        recognition.interimResults = false;

        // Обработчик результатов распознавания речи
        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            loadingIndicator.style.display = 'block';

            try {
                const response = await fetch('/process_voice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ voice_input: transcript })
                });

                if (!response.ok) throw new Error('Network response was not ok');
                
                const data = await response.json();
                
                // Находим ближайшее текстовое поле или textarea
                const activeElement = document.activeElement;
                let targetInput;
                
                if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                    targetInput = activeElement;
                } else {
                    // Если нет активного поля, используем последнее поле в форме
                    const inputs = document.querySelectorAll('textarea, input[type="text"]');
                    targetInput = inputs[inputs.length - 1];
                }

                if (targetInput) {
                    targetInput.value = data.processed_question;
                    // Сохраняем для анализа
                    voiceQuestionInput.value = JSON.stringify({
                        original: transcript,
                        processed: data.processed_question,
                        timestamp: new Date().toISOString()
                    });
                }

            } catch (error) {
                console.error('Voice processing error:', error);
                alert('Ошибка при обработке голосового ввода. Попробуйте еще раз.');
            } finally {
                loadingIndicator.style.display = 'none';
                voiceButton.disabled = false;
                voiceButton.innerHTML = '🎤 Голосовой ввод';
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            alert('Ошибка распознавания речи. Попробуйте еще раз.');
            voiceButton.disabled = false;
            voiceButton.innerHTML = '🎤 Голосовой ввод';
        };

        // Настройка кнопки голосового ввода
        voiceButton.addEventListener('click', () => {
            voiceButton.disabled = true;
            voiceButton.innerHTML = '🎤 Слушаю...';
            recognition.start();
        });
    } else {
        voiceButton.style.display = 'none';
        console.log('Speech recognition not supported');
    }

    // Настройка ChatGPT модального окна
    let isProcessing = false;
    
    const toggleModal = (show) => {
        chatModal.style.display = show ? 'block' : 'none';
        if (show) chatInput.focus();
    };

    chatButton.addEventListener('click', () => toggleModal(true));
    closeModalBtn.addEventListener('click', () => toggleModal(false));
    window.addEventListener('click', (e) => {
        if (e.target === chatModal) toggleModal(false);
    });

    const appendMessage = (message, isUser = false) => {
        const messageDiv = document.createElement('div');
        messageDiv.className = isUser ? 'user-message' : 'bot-message';
        messageDiv.textContent = message;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    // Обработка отправки сообщения ChatGPT
    const handleChatSubmit = async () => {
        if (isProcessing) return;

        const message = chatInput.value.trim();
        if (!message) return;

        try {
            isProcessing = true;
            loadingIndicator.style.display = 'block';
            chatInput.value = '';
            appendMessage(message, true);

            const response = await fetch('/chatgpt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();
            appendMessage(data.reply);

            // Сохраняем диалог
            const currentDialogs = chatgptQuestionsInput.value;
            const newDialog = `Q: ${message}\nA: ${data.reply}\n---\n`;
            chatgptQuestionsInput.value = currentDialogs + newDialog;

            // Если это помощь с формулировкой, предлагаем использовать ответ
            if (message.toLowerCase().includes('помог') || 
                message.toLowerCase().includes('сформулир')) {
                if (confirm('Использовать этот ответ в форме?')) {
                    // Находим активное или последнее поле ввода
                    const activeElement = document.activeElement;
                    let targetInput;
                    
                    if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                        targetInput = activeElement;
                    } else {
                        const inputs = document.querySelectorAll('textarea, input[type="text"]');
                        targetInput = inputs[inputs.length - 1];
                    }

                    if (targetInput) {
                        targetInput.value = data.reply;
                    }
                }
            }

        } catch (error) {
            console.error('ChatGPT error:', error);
            appendMessage('Произошла ошибка. Попробуйте еще раз.', false);
        } finally {
            isProcessing = false;
            loadingIndicator.style.display = 'none';
        }
    };

    chatSend.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSubmit();
        }
    });

    // Дополнительный функционал для формы
    const form = document.getElementById('survey-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            const requiredInputs = form.querySelectorAll('[required]');
            let isValid = true;

            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.classList.add('error');
                    setTimeout(() => input.classList.remove('error'), 3000);
                }
            });

            if (!isValid) {
                e.preventDefault();
                alert('Пожалуйста, заполните все обязательные поля');
            }
        });
    }
});
