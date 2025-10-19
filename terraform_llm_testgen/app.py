import streamlit as st
import os
import sys
import re
from openai import OpenAI
import anthropic
import google.generativeai as genai
from mistralai.client import MistralClient

def main():
    # ---------------------------
    # FORCE UTF-8 OUTPUT
    # ---------------------------
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ['GOOGLE_API_KEY'] = ''
    # ---------------------------
    # APP CONFIG
    # ---------------------------
    st.set_page_config(page_title="Terraform LLM Test Generator", layout="wide", page_icon="🧱")
    st.title("🧱 Terraform LLM Test Generator")
    st.caption("Generate Terraform `.tftest.hcl` cases and coverage reports using GPT, Claude, Gemini, Mistral, Hugging Face, or Mock mode.")

    # --- CSS for Sticky Sidebar Footer (FIXED) ---
    st.markdown("""
    <style>
    /* 1. Target the inner content block (stSidebarContent) and force flex layout */
    section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] {
        display: flex;
        flex-direction: column;
        height: 100%; /* CRITICAL: Ensures the content container fills the sidebar height */
    }

    /* 2. Position the footer content to push it to the bottom */
    .sidebar-footer-fixed {
        margin-top: auto; /* Pushes the element to the bottom edge of the flex container */
        padding-top: 1rem;
        text-align: center;
        border-top: 1px solid #e6e6e6;
        font-size: 0.75rem;
        color: #888;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

    # ---------------------------
    # SIDEBAR SETTINGS
    # ---------------------------
    st.sidebar.header("⚙️ Configuration")

    provider = st.sidebar.selectbox("Select Cloud Provider", ["Azure", "GCP", "Other"])
    service = st.sidebar.text_input("Enter Service (e.g., AKS, GKE, EC2, CloudSQL):", placeholder="AKS, GKE, etc.")
    target_coverage = st.sidebar.slider("Target Test Coverage (%)", 50, 100, 80, 5)

    llm_engine = st.sidebar.selectbox(
        "Select LLM Engine",
        ["gpt-5", "gpt-4o", "claude-3-5-sonnet", "gemini-2.5-pro", "mistral-large", "huggingface"]
    )

    test_mode = st.sidebar.radio("Select Test Mode", ["Mock Test (Simulated)", "Real Test (Runnable with terraform test)"])
    generate_button = st.sidebar.button("🚀 Generate Tests")

    # ---------------------------
    # FILE UPLOAD
    # ---------------------------
    st.subheader("📁 Upload Terraform Module")
    uploaded_files = st.file_uploader(
        "Upload Terraform files (`main.tf`, `variables.tf`, `outputs.tf`, etc.)",
        type=["tf", "tfvars"],
        accept_multiple_files=True
    )

    # ---------------------------
    # CLEAN TEXT FUNCTION
    # ---------------------------
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = text.replace("“", '\"').replace("”", '\"')
        text = text.replace("‘", "'").replace("’", "'")
        text = text.replace("–", "-").replace("—", "-")
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"\r\n|\r", "\n", text)
        return text

    # ---------------------------
    # PROMPT BUILDER FOR REAL TEST
    # ---------------------------
    def build_real_prompt(provider, service, target_coverage, files, test_mode):
        combined_code = ""
        for file in files:
            # Reset file pointer for reading
            file.seek(0)
            content = file.read().decode("utf-8", errors="ignore")
            combined_code += f"\n# File: {file.name}\n{content}\n"

        # Ensure file pointers are reset again in case this function is called multiple times
        for file in files:
            file.seek(0)

        prompt = f"""
    You are a Terraform testing expert.

    ### Objective
    Generate **Terraform `.tftest.hcl` test cases** for {provider} {service} 
    achieving **{target_coverage}% coverage**.

    ### Test Mode
    - Mode: **{test_mode}** (Runnable HCL tests)

    ### Requirements
    - Detect resources, variables, outputs
    - Generate runnable HCL tests
    - Output must strictly follow HCL syntax

    ### Files to Analyze
    {combined_code}

    ### Output Structure
    ## Resource and variable summary
    [Detailed analysis]

    ## Generated `.tftest.hcl` code block
    ```hcl
    [Your HCL test code here]
    ```

    ## Coverage summary
    [Coverage percentage and explanation]

    ## Improvement suggestions
    [Suggestions to improve coverage]
    """
        return prompt

    # ---------------------------
    # MOCK TEST GENERATOR (LLM-DRIVEN)
    # ---------------------------
    def generate_mock_test(provider, service, target_coverage, engine):
        """Generates a structured mock test output by calling the selected LLM with a simplified prompt."""
        mock_prompt = f"""
        You are generating a **simulated/mock test report** for the Terraform module that deploys {service} on {provider}.
        The test must be non-runnable and contain only placeholder values.

        **STRICTLY adhere to the mandatory output structure below and use the requested percentage.**

        ## Resource and variable summary
        This is a mock summary. The environment simulates the presence of core resources for the `{service}` service in the `{provider}` cloud.

        ## Generated `.tftest.hcl` code block
        ```hcl
        # MOCK TEST CASE: simulated_deployment_check
        test "simulated_deployment_check" {{
          variables {{
            environment = "dev"
            service_id = "mock-id-{service.lower()}"
          }}
          assert {{
            condition = true
            error_message = "This assertion is always true in mock mode."
          }}
        }}
        ```

        ## Coverage summary
        Based on the simulated analysis, the estimated coverage is **{target_coverage}%**. This is a simulated result for demonstration.

        ## Improvement suggestions
        1.  **Switch to Real Test:** Use the 'Real Test (Runnable)' mode to generate executable test cases.
        2.  **Define Outputs:** Clear outputs are required for robust, runnable test assertions.
        3.  **Parameterize Inputs:** Use input variables to control resource creation in real tests.
        """

        # The mock test is generated by calling the user-selected engine (or the proxy for huggingface)
        return call_llm(engine, mock_prompt)

    # ---------------------------
    # PARSE LLM OUTPUT
    # ---------------------------
    def parse_llm_result(llm_output: str) -> dict:
        sections = {
            'summary': 'Could not parse summary.',
            'code': 'No HCL code found.',
            'coverage': 'N/A',
            'suggestions': 'Could not parse suggestions.',
            'percentage': None
        }

        # 1. Extract HCL code block safely
        hcl_match = re.search(r"```hcl\\s*(.*?)\\s*```", llm_output, re.DOTALL | re.IGNORECASE)
        if hcl_match:
            code = hcl_match.group(1).strip()
        else:
            # Fallback for models that skip the markdown block
            code_search = re.search(r"## Generated `\\.tftest\\.hcl` code block\\s*(.*?)(##|$)", llm_output, re.DOTALL)
            if code_search:
                code = code_search.group(1).strip()
            else:
                code = "No HCL code found."

        sections['code'] = code

        # 2. Extract other sections
        pattern = re.compile(
            r"## Resource and variable summary\\s*(.*?)"
            r"## Coverage summary\\s*(.*?)"
            r"## Improvement suggestions\\s*(.*)", 
            re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(llm_output)
        if match:
            # Clean up sections by removing the code block content if it wasn't stripped by the regex
            sections['summary'] = match.group(1).strip()
            sections['coverage'] = match.group(2).strip()
            sections['suggestions'] = match.group(3).strip()

        # 3. Extract coverage percentage
        percentage_match = re.search(r"(\\d{1,3})%", sections['coverage'])
        if percentage_match:
            sections['percentage'] = int(percentage_match.group(1))

        return sections

    # ---------------------------
    # CALL LLM ROUTER
    # ---------------------------
    def call_llm(engine: str, prompt: str) -> str:
        try:
            system_prompt = "You are an expert in Terraform module testing. Follow the exact headers: '## Resource and variable summary', '## Generated .tftest.hcl code block', '## Coverage summary', and '## Improvement suggestions'."
            api_key_gcp = os.getenv("GOOGLE_API_KEY")
            if not api_key_gcp:
                raise EnvironmentError(
                    "GOOGLE_API_KEY environment variable not found. Please set it before running the script.\\n"
                    "Example: export GOOGLE_API_KEY='your_api_key_here' (Linux/Mac) or setx GOOGLE_API_KEY 'your_api_key_here' (Windows)"
                )
            # --- Standard LLM Engines ---
            if engine.startswith("gpt"):
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                resp = client.chat.completions.create(
                    model=engine,
                    messages=[{"role": "system", "content": system_prompt},{"role":"user","content":prompt}],
                    temperature=0.4,
                    max_tokens=2500,
                )
                return clean_text(resp.choices[0].message.content)

            elif engine.startswith("claude"):
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                msg = client.messages.create(model=engine, max_tokens=2500, temperature=0.4, system=system_prompt, messages=[{"role": "user", "content": prompt}])
                return clean_text(msg.content[0].text)

            elif engine.startswith("gemini"):
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                #genai.configure(api_key=api_key_gcp)
                model = genai.GenerativeModel(model_name=engine, system_instruction=system_prompt)
                resp = model.generate_content(prompt)
                return clean_text(resp.text)

            elif engine.startswith("mistral"):
                client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))
                resp = client.chat(model=engine, messages=[{"role":"system","content":system_prompt},{"role":"user","content":prompt}])
                return clean_text(resp.choices[0].message.content)

            # --- Hugging Face Proxy ---
            elif engine == "huggingface":
                # Simulation: Use a stable model (Gemini Flash) as a proxy for Hugging Face inference.
                if not os.getenv("HUGGINGFACE_API_KEY"):
                    st.warning("Hugging Face model selected. Using Gemini Flash as a stable proxy. Ensure HUGGINGFACE_API_KEY is conceptually set for a real deployment.")

                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash", 
                    system_instruction=system_prompt 
                )
                resp = model.generate_content(prompt)
                return clean_text(resp.text)

            else:
                return "❌ Unsupported LLM engine."

        except Exception as e:
            st.error(f"LLM call failed: {e}")
            return f"⚠️ Error with {engine}: {e}"

    # ---------------------------
    # DISPLAY RESULTS
    # ---------------------------
    def display_results(parsed_data: dict, test_mode: str):
        st.markdown("---")
        st.subheader(f"Test Generation Complete: {test_mode}")
        percentage = parsed_data.get('percentage')
        coverage_text = parsed_data.get('coverage', 'N/A')

        # Define colors for the metric
        if percentage is not None and percentage >= 75:
            color = "green"; emoji="🟢"
        elif percentage is not None and percentage >= 50:
            color = "orange"; emoji="🟡"
        else:
            color = "red"; emoji="🔴"

        st.markdown(f"""
            <style>
            .coverage-box {{ background-color:#f0f2f6; padding:15px; border-radius:8px; border-left:5px solid {color}; }}
            .coverage-value {{ font-size:2.5em; font-weight:bold; color:{color}; }}
            .coverage-label {{ font-size:0.9em; color:#6c757d; }}
            </style>
            """, unsafe_allow_html=True)

        col1, col2 = st.columns([1,3])
        with col1:
            st.markdown(f"<div class='coverage-box'><div class='coverage-label'>ESTIMATED COVERAGE</div><div class='coverage-value'>{percentage}%</div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"**{emoji} Coverage Analysis**\n{coverage_text}", unsafe_allow_html=True)

        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["📝 Generated HCL Test Code","📊 Resource Summary","💡 Improvement Suggestions"])
        with tab1:
            st.caption("Copy this code into `*.tftest.hcl`.")
            code = parsed_data.get('code', 'No HCL code found.')
            st.code(code, language="hcl")
        with tab2:
            st.info("Resource & variable summary")
            st.markdown(parsed_data.get('summary', ''), unsafe_allow_html=True)
        with tab3:
            st.warning("Improvement suggestions")
            st.markdown(parsed_data.get('suggestions', ''), unsafe_allow_html=True)

    # ---------------------------
    # MAIN ACTION
    # ---------------------------
    if generate_button and uploaded_files:
        result = ""
        with st.spinner(f"Generating {test_mode.lower()} for {provider} {service} using {llm_engine}..."):
            if "Mock" in test_mode:
                result = generate_mock_test(provider, service, target_coverage, llm_engine)
            else:
                prompt = build_real_prompt(provider, service, target_coverage, uploaded_files, test_mode)
                result = call_llm(llm_engine, prompt)

        st.success("✅ Test generation completed successfully!")
        parsed_data = parse_llm_result(result)
        display_results(parsed_data, test_mode)
        st.download_button(
            "💾 Download .tftest.hcl", 
            data=parsed_data.get('code', result), 
            file_name=f"{service.lower()}_{'mock' if 'Mock' in test_mode else 'real'}_test.tftest.hcl", 
            mime="text/plain"
        )
    else:
        st.info("Upload your Terraform module and click **Generate Tests** from the sidebar.")

    # ---------------------------
    # SIDEBAR FOOTER
    # ---------------------------
    # Using HTML/CSS class added above to ensure the footer is pushed to the very bottom
    st.sidebar.markdown('<div class="sidebar-footer-fixed">Terraform LLM Test Generator • Multi-Cloud • Multi-LLM • Hugging Face Support • v3.2</div>', unsafe_allow_html=True)


# def main():
    # """Entry point for the package CLI. Launches Streamlit running this file."""
    # import subprocess, pathlib
    # # Resolve to the installed package path to ensure streamlit runs the correct file
    # pkg_path = pathlib.Path(__file__).resolve()
    # subprocess.run(["streamlit", "run", str(pkg_path)])

if __name__ == "__main__":
    main()
