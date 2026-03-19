import { createBrowserRouter } from "react-router";
import { Root } from "./pages/Root";
import { Auth } from "./pages/Auth";
import { Dashboard } from "./pages/Dashboard";
import { StudentDashboard } from "./pages/StudentDashboard";
import { AssignmentDesigner } from "./pages/AssignmentDesigner";
import { AssignmentDetail } from "./pages/AssignmentDetail";
import { GradingPanel } from "./pages/GradingPanel";
import { KnowledgeBase } from "./pages/KnowledgeBase";
import { TeacherClassManager } from "./pages/TeacherClassManager";
import { NotFound } from "./pages/NotFound";

export const router = createBrowserRouter([
  {
    path: "/auth",
    Component: Auth,
  },
  {
    path: "/",
    Component: Root,
    children: [
      {
        index: true,
        Component: Dashboard,
      },
      {
        path: "student",
        Component: StudentDashboard,
      },
      {
        path: "create",
        Component: AssignmentDesigner,
      },
      {
        path: "classes",
        Component: TeacherClassManager,
      },
      {
        path: "assignment/:id",
        Component: AssignmentDetail,
      },
      {
        path: "grading/:id",
        Component: GradingPanel,
      },
      {
        path: "knowledge",
        Component: KnowledgeBase,
      },
      {
        path: "*",
        Component: NotFound,
      },
    ],
  },
]);
