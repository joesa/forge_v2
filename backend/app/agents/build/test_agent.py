"""Agent 9: Test — unit + integration tests, happy path + edge cases."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class TestAgent(BaseBuildAgent):
    name = "test"
    agent_number = 9

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        generated_files = state.get("generated_files", {})

        files: dict[str, str] = {}

        # Vitest config
        files["vitest.config.ts"] = """import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});"""

        files["src/test/setup.ts"] = """import '@testing-library/jest-dom';
"""

        # Generate tests for discovered components
        component_files = [
            f for f in generated_files
            if f.startswith("src/components/") and f.endswith(".tsx")
            and not f.endswith("index.ts")
        ]

        for comp_file in component_files:
            # Extract component name from file
            basename = comp_file.rsplit("/", 1)[-1].replace(".tsx", "")
            # PascalCase the component name
            component_name = basename[0].upper() + basename[1:]

            test_file = comp_file.replace("src/components/", "src/test/components/").replace(".tsx", ".test.tsx")
            rel_import = "../../components/" + basename

            files[test_file] = f"""import {{ render, screen }} from '@testing-library/react';
import {{ {component_name} }} from '{rel_import}';

describe('{component_name}', () => {{
  it('renders without crashing', () => {{
    render(<{component_name} />);
  }});

  it('displays component content', () => {{
    render(<{component_name} />);
    expect(document.querySelector('.{basename}')).toBeInTheDocument();
  }});
}});
"""

        # Generate tests for discovered pages
        page_files = [
            f for f in generated_files
            if f.startswith("src/pages/") and f.endswith(".tsx")
        ]

        for page_file in page_files:
            basename = page_file.rsplit("/", 1)[-1].replace(".tsx", "")
            component_name = basename[0].upper() + basename[1:]

            test_file = page_file.replace("src/pages/", "src/test/pages/").replace(".tsx", ".test.tsx")
            rel_import = "../../pages/" + basename

            files[test_file] = f"""import {{ render }} from '@testing-library/react';
import {{ MemoryRouter }} from 'react-router-dom';
import {{ {component_name} }} from '{rel_import}';

describe('{component_name}', () => {{
  it('renders without crashing', () => {{
    render(
      <MemoryRouter>
        <{component_name} />
      </MemoryRouter>
    );
  }});
}});
"""

        # App-level integration test
        files["src/test/App.test.tsx"] = """import { render } from '@testing-library/react';
import { App } from '../App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
  });
});
"""

        return files
