import { render, screen } from "@testing-library/react";
import { StatusLamp } from "./StatusLamp";

describe("StatusLamp", () => {
  it("shows the title, a state word and the detail", () => {
    render(
      <ul>
        <StatusLamp tone="warn" title="Trained model" state="Not loaded" detail="Missing model file(s)" />
      </ul>,
    );
    expect(screen.getByText("Trained model")).toBeInTheDocument();
    expect(screen.getByText("Not loaded")).toBeInTheDocument();
    expect(screen.getByText("Missing model file(s)")).toBeInTheDocument();
  });

  it("exposes the tone so styling does not depend on text", () => {
    const { container } = render(
      <ul>
        <StatusLamp tone="ok" title="Server" state="Running" />
      </ul>,
    );
    expect(container.querySelector("[data-tone='ok']")).not.toBeNull();
  });
});
