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
