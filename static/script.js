document.addEventListener('DOMContentLoaded', () => {
    // Элементы интерфейса для чата
    const chatButton = document.getElementById('chatgpt-button');
    const chatModal = document.getElementById('chatgpt-modal');
    const chatInput = document.getElementById('chatgpt-input');
    const chatSend = document.getElementById('chatgpt-send');
    const chatContainer = document.getElementById('chatgpt-chat');
    const chatgptQuestionsInput = document.getElementById('chatgpt_questions');
    const loadingIndicator = document.getElementById('loading-indicator');
    const closeModalBtn = document.querySelector('.close');

    // Элементы интерфейса для голосового ввода
    const voiceButton = document.getElementById('voice-button');
    const voiceModal = document.getElementById('voice-modal');
    const closeVoiceBtn = document.querySelector('.close-voice');
    const startVoiceBtn = document.getElementById('start-voice');
    const useVoiceResultBtn = document.getElementById('use-voice-result');
    const voiceIndicator = document.querySelector('.voice-indicator');
    const voiceStatusText = document.querySelector('.voice-status-text');
    const voiceOriginalText = document.getElementById('voice-original-text');
    const voiceProcessedText = document.getElementById('voice-processed-text');
    const voiceResult = document.querySelector('.voice-result');
    const voiceQuestionInput = document.getElementById('voice_question');

    // Функции модальных окон
    const toggleVoiceModal = (show) => {
        voiceModal.style.display = show ? 'block' : 'none';
        if (show) {
            voiceResult.classList.remove('show');
            voiceOriginalText.textContent = '';
            voiceProcessedText.textContent = '';
            voiceStatusText.textContent = 'Нажмите кнопку для начала записи';
            voiceIndicator.classList.remove('recording');
            useVoiceResultBtn.disabled = true;
        }
    };

    const toggleChatModal = (show) => {
        chatModal.style.display = show ? 'block' : 'none';
        if (show) chatInput.focus();
    };

    // Настройка обработчиков модальных окон
    voiceButton.addEventListener('click', () => toggleVoiceModal(true));
    closeVoiceBtn.addEventListener('click', () => toggleVoiceModal(false));
    chatButton.addEventListener('click', () => toggleChatModal(true));
    closeModalBtn.addEventListener('click', () => toggleChatModal(false));

    window.addEventListener('click', (e) => {
        if (e.target === voiceModal) toggleVoiceModal(false);
        if (e.target === chatModal) toggleChatModal(false);
    });

    // Настройка распознавания речи
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.lang = 'ru-RU';
        recognition.continuous = false;
        recognition.interimResults = false;

        startVoiceBtn.addEventListener('click', () => {
            voiceIndicator.classList.add('recording');
            voiceStatusText.textContent = 'Слушаю...';
            startVoiceBtn.disabled = true;
            recognition.start();
        });

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            voiceOriginalText.textContent = transcript;
            voiceStatusText.textContent = 'Обработка...';

            try {
                const response = await fetch('/process_voice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ voice_input: transcript })
                });

                if (!response.ok) throw new Error('Network response was not ok');

                const data = await response.json();
                voiceProcessedText.textContent = data.processed_question;
                voiceResult.classList.add('show');
                useVoiceResultBtn.disabled = false;
                voiceStatusText.textContent = 'Готово! Можете использовать результат или начать новую запись';

                // Сохраняем результат для анализа
                voiceQuestionInput.value = JSON.stringify({
                    original: transcript,
                    processed: data.processed_question,
                    timestamp: new Date().toISOString()
                });

            } catch (error) {
                console.error('Voice processing error:', error);
                voiceStatusText.textContent = 'Произошла ошибка. Попробуйте еще раз';
            } finally {
                voiceIndicator.classList.remove('recording');
                startVoiceBtn.disabled = false;
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            voiceStatusText.textContent = 'Ошибка распознавания. Попробуйте еще раз';
            voiceIndicator.classList.remove('recording');
            startVoiceBtn.disabled = false;
        };

        recognition.onend = () => {
            voiceIndicator.classList.remove('recording');
            startVoiceBtn.disabled = false;
        };

        // Обработчик кнопки использования результата
        useVoiceResultBtn.addEventListener('click', () => {
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
                targetInput.value = voiceProcessedText.textContent;
                toggleVoiceModal(false);
            }
        });

    } else {
        voiceButton.style.display = 'none';
        console.log('Speech Recognition API не поддерживается');
    }
    // Функционал ChatGPT
    let isProcessing = false;

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
