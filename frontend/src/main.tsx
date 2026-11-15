/** 새 프론트엔드 진입점. 출처: 사용자 신규 구현 요청. */
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/noto-sans-kr';
import App from './App';
import './styles.css';
createRoot(document.getElementById('root')!).render(<App />);
