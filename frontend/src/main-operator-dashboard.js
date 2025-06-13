// frontend/src/main-operator-dashboard.js
import { createApp } from 'vue';
import OperatorDashboardView from './views/OperatorDashboardView.vue';
import './style.css'; // Глобальні стилі

const appDiv = document.getElementById('qms-operator-dashboard');
if (appDiv) {
    createApp(OperatorDashboardView).mount(appDiv);
} else {
    console.error('Error: Could not find element with id "qms-operator-dashboard".');
}