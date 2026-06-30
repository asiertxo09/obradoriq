import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Simulate from "./Simulate";
import "./styles.css";

const root = document.getElementById("root")!;

if (window.location.pathname === "/simulate") {
  createRoot(root).render(<StrictMode><Simulate /></StrictMode>);
} else {
  createRoot(root).render(<StrictMode><App /></StrictMode>);
}
