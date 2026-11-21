import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// 不用 StrictMode：它会让 useEffect 跑两次，导致启动时重复创建会话
ReactDOM.createRoot(document.getElementById('root')).render(<App />)
