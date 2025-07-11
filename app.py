from h2o_wave import main, app, Q, ui
import uuid
import os
import tempfile
from h2ogpte import H2OGPTE
import logging
from fpdf import FPDF
from datetime import datetime

# Silence everything except your own logger
for noisy_logger in ['h2ogpte', 'urllib3', 'h2o', 'werkzeug', 'asyncio']:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Optional: suppress all loggers by default
logging.basicConfig(level=logging.CRITICAL)
global logger
# Then enable only your logger
logger = logging.getLogger('med-assist')
logger.setLevel(logging.DEBUG)

# GPTe configuration
GPTE_ENDPOINT = "https://h2ogpte.internal.dedicated.h2o.ai"
KEY = "--"  

def analyze_uploaded_documents(file_paths):
    """Analyze multiple uploaded documents and return a structured report"""
    try:
        # Validate file paths
        valid_file_paths = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.error(f"File not found at path: {file_path}")
                continue
                
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(f"File is empty: {file_path}")
                continue
                
            valid_file_paths.append(file_path)
        
        if not valid_file_paths:
            return "Error: No valid files were found. Please try uploading again."
        
        # Use unverified connection
        client = H2OGPTE(address=GPTE_ENDPOINT, api_key=KEY, verify=False)
        collection_id = client.create_collection(
            name=f'med_analysis_{uuid.uuid4()}',
            description='Medical document analysis'
        )
        
        upload_ids = []
        
        # Process each valid file
        for file_path in valid_file_paths:
            with open(file_path, 'rb') as f:
                file_name = os.path.basename(file_path)
                upload_id = client.upload(file_name, f)
                upload_ids.append(upload_id)
                logger.info(f"Uploaded file: {file_name}")
        
        if not upload_ids:
            return "Error: Failed to upload documents to the analysis engine."
        
        # Ingest all uploads
        client.ingest_uploads(collection_id, upload_ids)
        chat_session_id = client.create_chat_session(collection_id)
        
        with client.connect(chat_session_id) as session:
            reply = session.query(
                """Please analyze the uploaded medical document(s) and return a structured explanation using the format below.

            The input may contain **one or more documents**. If there are multiple, please **collate the findings** and present a unified report by intelligently merging related sections.

            Use Markdown-style formatting:
            - Headings should be written as ## Heading ##
            - Important terms or values should be enclosed in **double asterisks** for bold

            For each section, provide plain language explanations that a non-medical person can understand.

            ## Overview ##

            Please review the attached medical documents and provide a clear, easy-to-understand summary for the patient. Avoid medical jargon where possible.

                Include the following:

                What the results mean in simple terms

                Whether anything is abnormal or needs attention

                If any follow-up tests, treatments, or doctor visits are recommended - it should be summary where reading it the patient should have the effect of meeting the doctor and understanding the results.

        
            ## Key Findings ##
            Highlight the most important values, trends, or results. Explain what they suggest about the patient's overall health condition.

            ## Abnormal Results ##
            Call out any values outside the normal range or anything clinically significant. Briefly explain what they might mean. If multiple documents contain similar findings, group them meaningfully.

            ## Normal Results ##
            List key values that are within normal limits. Mention what this implies for the patient's health.

            ## Medical Terms Explained ##
            List and define any medical terms, abbreviations, or concepts mentioned in the documents. Keep explanations simple and accessible.

            ## Recommended Next Steps ##
            Provide actionable recommendations. These might include follow-up tests, consulting a specialist, or lifestyle adjustments based on the findings.

            Important:
            - Avoid unnecessary medical jargon.
            - Use simple, everyday language throughout.
            - When using medical terms, explain them clearly and contextually.
            - makesure to enclose the headings in ## Heading ## format - strictly follow the format.
            """)

        return reply.content

    except Exception as e:
        logger.error(f"Error in GPTe analysis: {str(e)}")
        return f"Error analyzing documents: {str(e)}"

from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import HRFlowable

def create_pdf_report(input_text):
    # Generate timestamped filename
    filename = f"medical_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Create a PDF document with the timestamped filename
    doc = SimpleDocTemplate(filename, pagesize=letter)
    
    # Prepare the story (content) for the PDF
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    heading_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontSize=18,
        leading=16,
        spaceAfter=12,
        textColor=colors.black,
        alignment=1 # center align
    )
    # Heading 2 style
    heading2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=14,
        spaceAfter=8,
        textColor=colors.darkblue,
        alignment=1 
    )

    # Custom styles
    heading3_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading3'],
        fontSize=12,
        leading=16,
        spaceAfter=4,
        textColor=colors.darkblue,
        alignment=0 # center align
    )


    # Caption style (smaller and gray text)
    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['BodyText'],
        fontSize=8,
        leading=10,
        spaceAfter=10,
        textColor=colors.grey,
        alignment=1  # center align
    )
        
    bold_style = ParagraphStyle(
        'BoldText',
        parent=styles['BodyText'],
        fontSize=10,
        leading=12,
        spaceAfter=2,
        textColor=colors.black,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['BodyText'],
        fontSize=10,
        leading=12,
        spaceAfter=2,
        textColor=colors.black
    )
    
    story.append(Paragraph("H2o Medical Center\n", heading_style))
    story.append(Paragraph("Lab Report Summary\n", heading2_style))
    story.append(Paragraph("This report is AI-generated and reviewed by a medical professional. Some details may be inaccurate or require clinical validation."
, caption_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceBefore=6, spaceAfter=6))
    # Process the input text line by line
    input_text = input_text.replace("According to the provided documents, here is a structured explanation of the medical findings:","")
    lines = input_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue  # skip empty lines
            
        if line.startswith('##') and line.endswith('##'):
            # This is a heading
            heading_text = line.strip('##').strip()
            story.append(Paragraph(heading_text, heading3_style))
        elif '**' in line:
            # This line contains bold text
            parts = line.split('**')
            processed_line = []
            
            for i, part in enumerate(parts):
                if i % 2 == 1:  # odd index means it was between **
                    processed_line.append(f'<b>{part}</b>')
                else:
                    processed_line.append(part)
                    
            combined = ''.join(processed_line)
            story.append(Paragraph(combined, normal_style))
        else:
            # Normal text
            story.append(Paragraph(line, normal_style))
        
        # Add small spacer after each element
        story.append(Spacer(1, 6))
    
    # Build the PDF
    doc.build(story)
    print(f"PDF report generated: {filename}")
    return filename


@app('/')
async def serve(q: Q):
    if not q.client.initialized:
        q.page['meta'] = ui.meta_card(box='', title='Med Assist with GPTe', theme='h2o-dark')
        q.page['header'] = ui.header_card(
            box='1 1 12 1',
            title='Med Assist with GPTe',
            subtitle='Upload your lab reports for AI-powered analysis',
            icon='HealthSolid',
            icon_color='#ff5722'
        )
        q.page['upload'] = ui.form_card(
            box='1 2 12 5',
            items=[
                ui.text_xl('Upload Medical Documents'),
                ui.file_upload(
                    name='document_upload',
                    label='Select Files for Analysis',
                    multiple=True,  # Enable multiple file selection
                    file_extensions=['pdf', 'jpg', 'jpeg', 'png', 'txt']
                ),
                ui.text_xs('Supported formats: PDF, JPG, PNG, TXT. You can select multiple files.')
            ]
        )
        q.client.initialized = True

    if q.args.document_upload:
        # Clean up previous cards - safely drop one by one
        try:
            q.page.drop('notification')
        except:
            pass
        try:
            q.page.drop('analysis')
        except:
            pass
        try:
            q.page.drop('download')
        except:
            pass
        
        # Show processing notification
        q.page['notification'] = ui.form_card(
            box='1 7 12 1',
            items=[
                ui.message_bar(type='info', text='Processing your documents, please wait...')
            ]
        )
        await q.page.save()
        
        try:
            uploaded_files = q.args.document_upload
            file_paths = []
            file_names = []
            
            # Process files properly using Wave's download method for paths
            if isinstance(uploaded_files, list):
                for file_info in uploaded_files:
                    if isinstance(file_info, str):  # It's a file path
                        file_name = os.path.basename(file_info)
                        # Use Wave's download method correctly
                        local_path = await q.site.download(file_info, tempfile.gettempdir())
                        if local_path:
                            file_paths.append(local_path)
                            file_names.append(file_name)
                    else:  # It's a file object
                        file_name = file_info.name
                        temp_file_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file_name}")
                        with open(temp_file_path, 'wb') as f:
                            f.write(file_info.content)
                        file_paths.append(temp_file_path)
                        file_names.append(file_name)
            else:  # Single file
                if isinstance(uploaded_files, str):
                    file_name = os.path.basename(uploaded_files)
                    local_path = await q.site.download(uploaded_files, tempfile.gettempdir())
                    if local_path:
                        file_paths.append(local_path)
                        file_names.append(file_name)
                else:
                    file_name = uploaded_files.name
                    temp_file_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file_name}")
                    with open(temp_file_path, 'wb') as f:
                        f.write(uploaded_files.content)
                    file_paths.append(temp_file_path)
                    file_names.append(file_name)
                
            if not file_paths:
                q.page['notification'] = ui.form_card(
                    box='1 7 12 1',
                    items=[
                        ui.message_bar(type='error', text='No valid files were processed. Please try uploading again.')
                    ]
                )
                await q.page.save()
                return

            logger.info(f"Processing {len(file_paths)} files: {file_names}")

            # Analyze all documents together
            analysis = analyze_uploaded_documents(file_paths)
            
            # Check if the analysis contains an error message
            if analysis.startswith("Error:"):
                q.page['notification'] = ui.form_card(
                    box='1 7 12 1',
                    items=[
                        ui.message_bar(type='error', text=analysis)
                    ]
                )
                await q.page.save()
                return

            # Store in client session
            q.client.file_paths = file_paths
            q.client.file_names = file_names
            q.client.analysis = analysis

            # Show success notification
            uploaded_list = '\n'.join([f"- {name}" for name in file_names])
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(type='success', text=f'Successfully processed {len(file_names)} file(s)')
                ]
            )

            # Show analysis results
            q.page['analysis'] = ui.form_card(
                box='1 8 12 6',
                items=[
                    ui.text_xl('Medical Analysis Results'),
                    ui.text_l(f'Documents analyzed: {", ".join(file_names)}'),
                    ui.textbox(
                        name='analysis_text',
                        label='AI-Generated Report (editable):',
                        value=q.client.analysis,
                        multiline=True,
                        height='400px',
                        spellcheck=True,
                    ),
                    ui.buttons([
                        ui.button(name='regenerate_button', label='Regenerate Analysis'),
                        ui.button(name='download_button', label='Download Report as PDF', primary=True),
                        ui.button(name='new_upload_button', label='Upload New Documents')
                    ])
                ]
            )

        except Exception as e:
            logger.error(f"File processing error: {str(e)}", exc_info=True)
            error_message = f"Error processing files: {str(e)}"
            if "permission" in str(e).lower():
                error_message = "Permission error: Unable to save or read the files."
            elif "format" in str(e).lower():
                error_message = "Format error: One or more file formats may not be supported."
            
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(type='error', text=error_message)
                ]
            )

    if q.args.download_button:
        try:
            # Get the current analysis text (may have been edited by user)
            analysis_content = q.args.analysis_text or q.client.analysis
            file_names = q.client.file_names
            
            if not analysis_content or analysis_content.startswith("Error:"):
                q.page['download'] = ui.form_card(
                    box='1 15 12 1',
                    items=[
                        ui.message_bar(type='error', text='Cannot generate PDF: No valid analysis to include.')
                    ]
                )
                await q.page.save()
                return
            
            # Create PDF report
            pdf_filename = create_pdf_report(analysis_content)
            
            if pdf_filename:
                # Upload PDF to Wave server and provide download link
                download_path, = await q.site.upload([pdf_filename])
                q.page['download'] = ui.form_card(
                    box='1 15 12 3',
                    items=[
                        ui.message_bar(type='success', text='Medical report generated successfully!'),
                        ui.link(label='Download Medical Report PDF', path=download_path,button=True,download=True)
                    ]
                )
                
                # Clean up temporary PDF file
                try:
                    os.remove(pdf_filename)
                except:
                    pass
            else:
                q.page['download'] = ui.form_card(
                    box='1 15 12 1',
                    items=[
                        ui.message_bar(type='error', text='Failed to generate PDF report.')
                    ]
                )
                
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            q.page['download'] = ui.form_card(
                box='1 15 12 1',
                items=[
                    ui.message_bar(type='error', text=f'Error generating PDF: {str(e)}')
                ]
            )

    if q.args.regenerate_button:
        if hasattr(q.client, 'file_paths') and q.client.file_paths:
            # Show processing notification
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(type='info', text='Regenerating analysis, please wait...')
                ]
            )
            await q.page.save()
            
            try:
                analysis = analyze_uploaded_documents(q.client.file_paths)
                
                # Check if the analysis contains an error message
                if analysis.startswith("Error:"):
                    q.page['notification'] = ui.form_card(
                        box='1 7 12 1',
                        items=[
                            ui.message_bar(type='error', text=analysis)
                        ]
                    )
                    await q.page.save()
                    return
                    
                q.client.analysis = analysis
                
                # Update the analysis textbox
                q.page['analysis'].items[2].value = analysis
                
                q.page['notification'] = ui.form_card(
                    box='1 7 12 1',
                    items=[
                        ui.message_bar(type='success', text='Analysis regenerated successfully.')
                    ]
                )
            except Exception as e:
                logger.error(f"Regeneration error: {str(e)}")
                q.page['notification'] = ui.form_card(
                    box='1 7 12 1',
                    items=[
                        ui.message_bar(type='error', text=f'Failed to regenerate analysis: {str(e)}')
                    ]
                )

    if q.args.new_upload_button:
        # Clear client session data
        for key in ['file_paths', 'file_names', 'analysis', 'file_content']:
            if hasattr(q.client, key):
                delattr(q.client, key)
        
        # Remove analysis and download cards - safely drop one by one
        try:
            q.page.drop('analysis')
        except:
            pass
        try:
            q.page.drop('notification')
        except:
            pass
        try:
            q.page.drop('download')
        except:
            pass
        
        # Reset upload form
        q.page['upload'].items[1].value = None

    await q.page.save()

if __name__ == '__main__':
    main()
