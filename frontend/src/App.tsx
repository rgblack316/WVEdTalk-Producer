import { Routes, Route, Outlet } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AuthGate from "@/components/AuthGate";
import Home from "@/pages/Home";
import Archive from "@/pages/Archive";
import BriefingPage from "@/pages/BriefingPage";
import StoryDetail from "@/pages/StoryDetail";
import Candidates from "@/pages/Candidates";
import Settings from "@/pages/Settings";
import Users from "@/pages/Users";
import Episodes from "@/pages/Episodes";
import EpisodePage from "@/pages/EpisodePage";
import SharedBriefing from "@/pages/SharedBriefing";
import Subscribe from "@/pages/Subscribe";
import SubmitStory from "@/pages/SubmitStory";
import Submissions from "@/pages/Submissions";
import Unsubscribe from "@/pages/Unsubscribe";

// Everything under ProtectedLayout sits behind the login gate; /share/* is public.
function ProtectedLayout() {
  return (
    <AuthGate>
      <Outlet />
    </AuthGate>
  );
}

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/share/briefing/:date" element={<SharedBriefing />} />
        <Route path="/subscribe" element={<Subscribe />} />
        <Route path="/submit" element={<SubmitStory />} />
        <Route path="/unsubscribe" element={<Unsubscribe />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/submissions" element={<Submissions />} />
          <Route path="/episodes" element={<Episodes />} />
          <Route path="/episodes/:week" element={<EpisodePage />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/users" element={<Users />} />
          <Route path="/briefings/:date" element={<BriefingPage />} />
          <Route path="/briefings/:date/stories/:storyId" element={<StoryDetail />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}
