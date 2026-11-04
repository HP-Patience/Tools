import React from "react";
import ReactDOM from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./styles/global.css";
import App from "./App";
class AppBoundary extends React.Component<
  React.PropsWithChildren,
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main style={{ padding: 40, fontFamily: "sans-serif" }}>
          <h1>地图暂时无法显示</h1>
          <p>数据文件不会被修改。请刷新页面，或回到电脑检查项目。</p>
          <button onClick={() => location.reload()}>重新加载</button>
        </main>
      );
    return this.props.children;
  }
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppBoundary>
      <App />
    </AppBoundary>
  </React.StrictMode>,
);
