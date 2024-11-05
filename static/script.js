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

    // Функционал голосового ввода
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
        const recognition = new SpeechRecognition();
        
        // Настройки распознавания
        recognition.lang = 'ru-RU';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            console.log('Распознавание голоса запущено');
            voiceButton.classList.add('listening');
            loadingIndicator.style.display = 'block';
        };

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Распознанный текст:', transcript);

            try {
                const response = await fetch('/process_voice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ voice_input: transcript })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                console.log('Обработанный текст:', data);

                // Находим активное текстовое поле
                const activeElement = document.activeElement;
                let targetInput;

                if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                    targetInput = activeElement;
                } else {
                    const inputs = document.querySelectorAll('textarea, input[type="text"]');
                    targetInput = inputs[inputs.length - 1];
                }

                // Вставляем обработанный текст
                if (targetInput) {
                    targetInput.value = data.processed_question;
                    // Сохраняем для анализа
                    voiceQuestionInput.value = JSON.stringify({
                        original: transcript,
                        processed: data.processed_question,
                        timestamp: new Date().toISOString()
                    });
                    
                    // Анимация успешного распознавания
                    targetInput.classList.add('voice-input-success');
                    setTimeout(() => {
                        targetInput.classList.remove('voice-input-success');
                    }, 1000);
                }

            } catch (error) {
                console.error('Ошибка обработки голосового ввода:', error);
                alert('Произошла ошибка при обработке голосового ввода. Попробуйте еще раз.');
            } finally {
                loadingIndicator.style.display = 'none';
                voiceButton.classList.remove('listening');
                voiceButton.disabled = false;
                voiceButton.innerHTML = '🎤 Голосовой ввод';
            }
        };

        recognition.onerror = (event) => {
            console.error('Ошибка распознавания речи:', event.error);
            alert('Ошибка распознавания речи. Пожалуйста, проверьте доступ к микрофону и попробуйте снова.');
            loadingIndicator.style.display = 'none';
            voiceButton.classList.remove('listening');
            voiceButton.disabled = false;
            voiceButton.innerHTML = '🎤 Голосовой ввод';
        };

        recognition.onend = () => {
            console.log('Распознавание голоса завершено');
            voiceButton.classList.remove('listening');
            voiceButton.disabled = false;
            voiceButton.innerHTML = '🎤 Голосовой ввод';
            loadingIndicator.style.display = 'none';
        };

        voiceButton.addEventListener('click', () => {
            voiceButton.disabled = true;
            voiceButton.innerHTML = '🎤 Слушаю...';
            recognition.start();
        });

    } else {
        voiceButton.style.display = 'none';
        console.log('Speech Recognition API не поддерживается в этом браузере');
    }

    // Функционал ChatGPT
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
        
        const divider = document.createElement('div');
        divider.className = 'message-divider';
        
        chatContainer.appendChild(messageDiv);
        chatContainer.appendChild(divider);
        
        chatContainer.scrollTop = chatContainer.scrollHeight;

        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';
        
        requestAnimationFrame(() => {
            messageDiv.style.transition = 'all 0.3s ease';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        });
    };

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

            const currentDialogs = chatgptQuestionsInput.value;
            const newDialog = `Q: ${message}\nA: ${data.reply}\n---\n`;
            chatgptQuestionsInput.value = currentDialogs + newDialog;

        } catch (error) {
            console.error('ChatGPT error:', error);
            appendMessage('Произошла ошибка. Попробуйте еще раз.', false);
        } finally {
            isProcessing = false;
            loadingIndicator.style.display = 'none';
            chatInput.focus();
        }
    };

    chatSend.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSubmit();
        }
    });

    // Валидация формы
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
