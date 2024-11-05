// Проверка поддержки SpeechRecognition API
window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const voiceButton = document.getElementById('voice-button');
const voiceQuestionInput = document.getElementById('voice_question');
const loadingIndicator = document.getElementById('loading-indicator');

if ('SpeechRecognition' in window) {
  const recognition = new SpeechRecognition();
  recognition.lang = 'ru-RU';
  recognition.interimResults = false;

  voiceButton.onclick = function() {
    recognition.start();
  }

  recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript;

    // Показать индикатор загрузки
    loadingIndicator.style.display = 'block';

    fetch('/process_voice', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json;charset=utf-8'
      },
      body: JSON.stringify({voice_input: transcript})
    })
    .then(response => response.json())
    .then(data => {
      // Скрыть индикатор загрузки
      loadingIndicator.style.display = 'none';

      alert('Откорректированный вопрос: ' + data.corrected_question);
      voiceQuestionInput.value = data.corrected_question;
    })
    .catch(error => {
      loadingIndicator.style.display = 'none';
      alert('Ошибка при обработке голосового ввода.');
    });
  }

  recognition.onerror = function(event) {
    alert('Ошибка при распознавании речи: ' + event.error);
  }
} else {
  voiceButton.disabled = true;
  voiceButton.textContent = 'Голосовой ввод не поддерживается';
  alert('Ваш браузер не поддерживает голосовой ввод. Пожалуйста, используйте текстовый ввод.');
}

// Работа с модальным окном чата
const modal = document.getElementById('chatgpt-modal');
const chatBtn = document.getElementById('chatgpt-button');
const closeBtn = document.getElementsByClassName('close')[0];
const chatInput = document.getElementById('chatgpt-input');
const chatSend = document.getElementById('chatgpt-send');
const chatContainer = document.getElementById('chatgpt-chat');
const chatgptQuestionsInput = document.getElementById('chatgpt_questions');

chatBtn.onclick = function() {
  modal.style.display = 'block';
}

closeBtn.onclick = function() {
  modal.style.display = 'none';
}

window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = 'none';
  }
}

function appendMessage(message, className) {
  const messageDiv = document.createElement('div');
  messageDiv.className = className;
  messageDiv.textContent = message;
  chatContainer.appendChild(messageDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

chatSend.onclick = function() {
  const message = chatInput.value;
  if (message.trim() !== '') {
    // Показать индикатор загрузки
    loadingIndicator.style.display = 'block';

    appendMessage(message, 'user-message');

    fetch('/chatgpt', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json;charset=utf-8'
      },
      body: JSON.stringify({message: message})
    })
    .then(response => response.json())
    .then(data => {
      // Скрыть индикатор загрузки
      loadingIndicator.style.display = 'none';

      appendMessage(data.reply, 'bot-message');

      // Сохранить диалог в скрытом поле
      chatgptQuestionsInput.value += `User: ${message}\nChatGPT: ${data.reply}\n`;
    })
    .catch(error => {
      loadingIndicator.style.display = 'none';
      alert('Ошибка при обращении к серверу.');
    });

    chatInput.value = '';
  }
}
