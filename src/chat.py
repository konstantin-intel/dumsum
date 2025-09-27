import argparse
import json
import os
from typing import Final
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, \
    HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage

from common import get_data_file
import logging

# create logger
logger = logging.getLogger('dumsum')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s',  datefmt='%Y-%m-%d %H:%M:%S')


HR_FILE: Final = "hr.md"
HR_FALLBACK_FILE: Final = "hr-fallback.md"
SKILLS_FILE: Final = "skills.md"
RESUME_FILE: Final = "data/_resume.md"       # should use user updated resume file
IGNORE_FILE: Final = "data/_ignore.txt"      # file with ignored companies
DEFAULTS: Final = "data/_defaults.yaml"
URLS_FILE: Final = "data/_urls.txt"
DEFAULTS_SYSTEM_FILE: Final = "defaults-system.md"
DEFAULTS_USER_FILE: Final = "defaults-user.md"

def read_file_content(file_path: str) -> str | None:
    with open(file_path, 'r') as file:
        return file.read()

def extract_between_markers(text: str, marker1: str, marker2: str) -> str | None:
    start = text.find(marker1)
    if start == -1:
        return None
    start += len(marker1)
    end = text.find(marker2, start)
    if end == -1:
        return None
    return text[start:end]

def _chat():
    formatter=logging.Formatter("%(asctime)s %(message)s")
    # create log file for the chat
    fh = logging.FileHandler('chat.log')        
    fh.setFormatter(formatter)
    # create console logger
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    # register
    logger.addHandler(fh)
    logger.addHandler(ch)
    if key:=os.environ.get("XAI_API_KEY"):
        logger.info("Using XAI")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=key,
            base_url="https://api.x.ai/v1/",
            model=os.getenv("XAI_MODEL", "grok-beta"),
            temperature=0.1,
            seed=1234,
        )

    if key:=os.environ.get("GROQ_API_KEY"):
        logger.info("Using Groq")
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=key,
            # model="llama-3.2-3b-preview",
            model=os.getenv("GROQ_MODEL", "deepseek-r1-distill-llama-70b"),
            temperature=0.1,
        )

    if key:=os.environ.get("ANTHROPIC_API_KEY"):    
        logger.info("Using Anthropic")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=key,
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            temperature=0.0,
        )

    if key:=os.environ.get("GITHUB_TOKEN"):
        # check https://github.com/marketplace/models
        logger.info("Using GithubOpenAI")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=key,
            # model="gpt-4o",
            model=os.getenv("GITHUB_MODEL", "gpt-4o-mini"),
            temperature=0.1,
            seed=100,
        )
    
    if key:=os.environ.get("GOOGLE_API_KEY"):
        logger.info("Using ChatGoogle")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", 'gemini-2.0-flash'),
            api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=0.1,
        )

    if key:=os.environ.get("OPENAI_API_KEY"):
        logger.info("Using OpenAI")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.1,
            seed=100,
        )
    
    # if key:=os.environ.get("ALIBABA_API_KEY"):
    #     logger.info("Using Alibaba")
    #     from langchain_openai import ChatOpenAI
    #     return ChatOpenAI(
    #         api_key=key,
    #         model=os.getenv("ALIBABA_MODEL", "qwen-turbo"),
    #         base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    #         temperature=0.1,
    #         seed=100,
    #     )
    
    if key:=os.environ.get("OPENROUTER_API_KEY"):
        logger.info("Using Openrouter")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=key,
            model=os.getenv("OPENROUTER_MODEL", "qwen/qwq-32b:free"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
            seed=100,
        )

    if key:=os.environ.get("DEEPSEEK_API_KEY"):
        logger.info("Using DeepSeek")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=key,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url="https://api.deepseek.com",
            temperature=0.1,
            seed=100,
        )

    if key:=os.environ.get("GPT4FREE_KEY"):
        logger.info("Using Gpt4free")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=key,
            model=os.getenv("GPT4FREE_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("GPT4FREE_HOST", "http://localhost:8080/v1"),
            temperature=0.1,
            seed=100,
        )

    logger.info("Using Ollama")
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:latest",),
        temperature=0.0,
        num_ctx=16192,
        seed=100,
        keep_alive="15m", 
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434",),
    )

def matcher(job: str):
    chat = _chat()
    system = SystemMessagePromptTemplate.from_template_file(
        get_data_file(HR_FILE), ['JOB_DESCRIPTION']).format(JOB_DESCRIPTION=job,)    
    user = HumanMessagePromptTemplate.from_template_file(RESUME_FILE, []).format()                                                       
    prompt_template = ChatPromptTemplate.from_messages([system, user])
    try:
        chain = prompt_template | chat | JsonOutputParser() 
        res = chain.invoke({})
        # logger.info(res)
        return res
    except Exception as ex:
        logger.info(f"Error decoding JSON: {ex}")
        # after hallucination take ex and call chat to convert response to json structure with expected format
        return matcher_fallback(ex.args[0])

def matcher_fallback(answer: str):
    chat = _chat()
    system = SystemMessagePromptTemplate.from_template_file(get_data_file(HR_FALLBACK_FILE), []).format()    
    user = HumanMessage(content=answer)                                                       
    prompt_template = ChatPromptTemplate.from_messages([system, user])
    try:
        chain = prompt_template | chat | JsonOutputParser() 
        res = chain.invoke({})
        # logger.info(res)
        return res
    except Exception as ex:
        logger.info(f"Error decoding JSON: {ex}")
        return None    

def answer(skill:str, options: list = []) -> dict:
    chat = _chat()
    system = SystemMessagePromptTemplate.from_template_file(
        get_data_file(SKILLS_FILE), ['RESUME', 'SKILLS']).format(
            RESUME=read_file_content(RESUME_FILE),
            SKILLS=read_file_content(DEFAULTS), )
    user = HumanMessagePromptTemplate.from_template_file(
        get_data_file(DEFAULTS_USER_FILE), ['QUESTION', 'OPTIONS']).format(
            QUESTION=skill, 
            OPTIONS="\n".join([f"- {i}" for i in options]))
    prompt_template = ChatPromptTemplate.from_messages([system, user])
    try:
        chain = prompt_template | chat | JsonOutputParser() 
        res = chain.invoke({})
        # logger.info(res)
        return res
    except Exception as ex:
        logger.info(f"Error decoding JSON: {ex}")
        return None    

# testing
if __name__ == "__main__":
    def _main_chat():
        parser = argparse.ArgumentParser(description="Chat with AI")
        parser.add_argument("-j", required=False, type=str, help="Job description file")
        parser.add_argument("-s", required=False, type=str, help="skill")
        parser.add_argument("-f", required=False, type=str, help="fallback")
        parser.add_argument('-a', nargs='*', help='An array of values')
        args = parser.parse_args()
        if hasattr(args, 'j') and args.j:
            return matcher(read_file_content(args.j))
        if hasattr(args, 'f') and args.f:
            return matcher_fallback(args.f)
        if hasattr(args, 's') and args.s:
            return answer(args.s, args.a if args.a else [])
    
    if os.path.exists(".key"):
        from dotenv import load_dotenv
        load_dotenv(".key")
        
    logger.info(f"{_main_chat()}")