import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AuthGate from "@/components/AuthGate";
import Home from "@/pages/Home";
import Archive from "@/pages/Archive";
import BriefingPage from "@/pages/BriefingPage";
import StoryDetail from "@/pages/StoryDetail";
import Candidates from "@/pages/Candidates";
import Settings from "@/pages/Settings";
import Episodes from "@/pages/Episodes";
import EpisodePage from "@/pages/EpisodePage";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <AuthGate>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/episodes" element={<Episodes />} />
          <Route path="/episodes/:week" element={<EpisodePage />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/briefings/:date" element={<BriefingPage />} />
          <Route path="/briefings/:date/stories/:storyId" element={<StoryDetail />} />
        </Routes>
      </AuthGate>
      <Toaster />
    </>
  );
}
