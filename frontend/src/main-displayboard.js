// qms_cherga/frontend/src/main-displayboard.js
import { createApp } from 'vue'
import DisplayBoardView from './views/DisplayBoardView.vue'
import './style.css' // Ваші глобальні стилі, включаючи Tailwind

const displayBoardAppDiv = document.getElementById('app-display-board');
if (displayBoardAppDiv) {
    createApp(DisplayBoardView).mount(displayBoardAppDiv);
} else {
    console.error('Error: Could not find element with id "app-display-board" to mount DisplayBoardView.');
}