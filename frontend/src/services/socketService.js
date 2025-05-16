// frontend/src/services/socketService.js
import { ref, computed } from 'vue';
import io from 'socket.io-client'; // Імпортуємо io напряму
import { socketio_port } from '../../../../../sites/common_site_config.json'

let socket = null; // Єдиний екземпляр сокету
const connected = ref(false);
const currentOfficeIdForRoom = ref(null); // Зберігаємо ID офісу для поточної кімнати
const office_room = (office_name) => "qms_office:" + office_name;
// Функція для отримання URL сокет-сервера
function getSocketUrl() {
    let host = window.location.hostname
    let siteName = window.frappe?.boot?.sitename
    let port = window.location.port ? `:${socketio_port}` : ''
    let protocol = port ? 'http' : 'https'
    let url = `${protocol}://${host}${port}/${siteName}`
    return url;
}

export function useSocket() {

    const initSocket = (officeId) => {
        if (socket && socket.connected && currentOfficeIdForRoom.value === officeId) {
            console.log(`[SocketService] Already connected to room for office: ${officeId}. Re-joining room just in case.`);
            // Навіть якщо підключено, краще пере-приєднатися до кімнати, якщо officeId той самий,
            // на випадок, якщо з'єднання з кімнатою було втрачено на сервері, а клієнт про це не знає.
            const roomName = office_room(officeId);
            socket.emit('join_room', roomName);
            return socket;
        }

        if (socket) {
            console.log(`[SocketService] Disconnecting existing socket before re-initializing for office: ${officeId}`);
            socket.disconnect();
            socket = null; // Важливо скинути старий сокет
        }

        const socketUrl = getSocketUrl();
        if (!socketUrl) {
            connected.value = false;
            return null;
        }

        currentOfficeIdForRoom.value = officeId; // Зберігаємо officeId для поточної кімнати

        console.log(`[SocketService] Initializing socket connection to ${socketUrl} for office ${officeId}`);
        socket = io(socketUrl, {
            reconnectionAttempts: 5,
            timeout: 20000,
            path: '/socket.io/',
            transports: ['websocket'], // Починаємо з websocket
            withCredentials: true,
            // Важливо для Frappe, особливо якщо є автентифікація
            // forceNew: true, // Може бути корисним для уникнення проблем з кешуванням з'єднань, але використовуйте обережно
        });

        socket.on('connect', () => {
            connected.value = true;
            console.log('[SocketService] Socket connected. SID:', socket.id);
            if (currentOfficeIdForRoom.value) { // Переконуємося, що officeId встановлено
                const roomName = office_room(currentOfficeIdForRoom.value);
                socket.emit('join_room', roomName);
                console.log(`[SocketService] Emitted 'join_room' for: ${roomName}`);
            }
        });

        socket.on('disconnect', (reason) => {
            connected.value = false;
            // Не скидаємо currentOfficeIdForRoom.value тут, щоб при перепідключенні знати, до якої кімнати підключатися
            console.warn('[SocketService] Socket disconnected. Reason:', reason);
            if (reason === 'io server disconnect') {
                // Спроба перепідключення може бути доцільною
                // socket.connect(); // socket.io-client робить це автоматично, якщо reconnection: true (за замовчуванням)
            }
        });

        socket.on('connect_error', (error) => {
            connected.value = false;
            console.error('[SocketService] Socket connection error:', error.message, error.data || error);
        });

        socket.on('reconnect_attempt', (attempt) => {
            console.info(`[SocketService] Reconnect attempt #${attempt}`);
        });
        socket.on('reconnect_failed', () => {
            console.error('[SocketService] Failed to reconnect after multiple attempts.');
            connected.value = false;
        });
        socket.on('reconnect_error', (error) => {
            console.error('[SocketService] Reconnection error:', error);
            connected.value = false;
        });
        socket.on('reconnect', (attempt) => {
            connected.value = true; // Встановлюємо true після успішного перепідключення
            console.info(`[SocketService] Reconnected after ${attempt} attempts. SID: ${socket.id}`);
            if (currentOfficeIdForRoom.value) {
                const roomName = office_room(currentOfficeIdForRoom.value);
                socket.emit('join_room', roomName);
                console.info(`[SocketService] Re-emitted 'join_room' for ${roomName} after reconnect.`);
            }
        });


        // Обробники для дебагу кімнат
        socket.on('room_joined', (room) => {
            console.log(`[SocketService] Successfully joined room: ${room}`);
        });
        socket.on('room_left', (room) => {
            console.log(`[SocketService] Left room: ${room}`);
        });
        socket.on('room_join_error', (errorData) => {
            console.error(`[SocketService] Error joining room: `, errorData.room, errorData.error);
        });
        socket.on('event_permission_error', (errorData) => {
            console.error(`[SocketService] Event permission error: `, errorData.event, errorData.room, errorData.error);
        });

        // Загальний обробник для всіх подій (корисно для дебагу)
        socket.onAny((eventName, ...args) => {
            if (eventName !== 'display_board_pong_ack') { // Щоб не засмічувати консоль понгами, якщо вони часті
                console.log(`[SocketService DEBUG] Event received - Name: '${eventName}', Args:`, args);
            }
        });


        return socket;
    };

    const listen = (eventName, callback) => {
        if (socket) {
            // Видаляємо попередні слухачі, щоб уникнути дублювання при гарячому перезавантаженні
            socket.off(eventName, callback); // Спочатку видаляємо, потім додаємо
            socket.on(eventName, callback);
            console.log(`[SocketService] Listening to event: ${eventName}`);
        } else {
            console.warn(`[SocketService] Socket not initialized. Cannot listen to event: ${eventName}`);
        }
    };

    // Функція для відписки від події
    const off = (eventName, callback) => {
        if (socket) {
            socket.off(eventName, callback);
            console.log(`[SocketService] Unsubscribed from event: ${eventName}`);
        }
    };

    const emitEvent = (eventName, data) => { // Перейменовано, щоб уникнути конфлікту з `emit` з Vue
        if (socket && socket.connected) {
            socket.emit(eventName, data);
            console.log(`[SocketService] Emitted event '${eventName}' with data:`, data);
        } else {
            console.warn(`[SocketService] Socket not connected. Cannot emit event: ${eventName}`);
        }
    };

    const disconnectSocket = () => {
        if (socket) {
            if (currentOfficeIdForRoom.value) {
                const roomName = office_room(currentOfficeIdForRoom.value);
                // socket.emit('leave_room', roomName); // Frappe обробляє це автоматично при disconnect
                console.log(`[SocketService] Preparing to disconnect from room for office: ${currentOfficeIdForRoom.value}`);
            }
            socket.disconnect();
            // socket = null; // Не скидаємо тут, щоб connected.value оновився через 'disconnect'
            console.log('[SocketService] Socket disconnect called.');
        }
        // Скидання стану після відключення
        connected.value = false;
        currentOfficeIdForRoom.value = null;
    };

    return {
        socketInstance: computed(() => socket), // Повертаємо як computed, щоб було реактивним, хоча сам об'єкт сокета не є глибоко реактивним
        connected,
        currentOfficeId: currentOfficeIdForRoom, // Перейменовано для ясності на стороні компонента
        initSocket,
        listen,
        off, // Додано функцію відписки
        emitEvent, // Використовуйте цю функцію для надсилання подій
        disconnectSocket
    };
}