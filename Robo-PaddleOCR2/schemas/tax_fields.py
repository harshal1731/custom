from pydantic import BaseModel, Field
from typing import Optional

class W2Fields(BaseModel):
    year: Optional[str] = Field(None, description="Tax Year")
    employee_ssn: Optional[str] = Field(None, description="Employee’s social security number (111-11-1111)")
    employer_ein: Optional[str] = Field(None, description="Employer identification number (11-1111111)")
    employer_name_address: Optional[str] = Field(None, description="Employer’s name, address, and ZIP code")
    wages_tips_other_comp: Optional[float] = Field(None, description="Box 1: Wages, tips, other compensation")
    federal_income_tax_withheld: Optional[float] = Field(None, description="Box 2: Federal income tax withheld")
    social_security_wages: Optional[float] = Field(None, description="Box 3: Social security wages")
    social_security_tax_withheld: Optional[float] = Field(None, description="Box 4: Social security tax withheld")
    medicare_wages_and_tips: Optional[float] = Field(None, description="Box 5: Medicare wages and tips")
    medicare_tax_withheld: Optional[float] = Field(None, description="Box 6: Medicare tax withheld")

class Form1099INTFields(BaseModel):
    year: Optional[str] = Field(None, description="Tax Year")
    payer_tin: Optional[str] = Field(None, description="Payer's TIN (11-1111111)")
    recipient_tin: Optional[str] = Field(None, description="Recipient's TIN (111-11-1111)")
    payer_name: Optional[str] = Field(None, description="Payer's name")
    interest_income: Optional[float] = Field(None, description="Box 1: Interest income")
    early_withdrawal_penalty: Optional[float] = Field(None, description="Box 2: Early withdrawal penalty")
    interest_on_us_savings_bonds: Optional[float] = Field(None, description="Box 3: Interest on U.S. Savings Bonds and Treasuries")
    federal_income_tax_withheld: Optional[float] = Field(None, description="Box 4: Federal income tax withheld")

class Form1099DIVFields(BaseModel):
    year: Optional[str] = Field(None, description="Tax Year")
    payer_tin: Optional[str] = Field(None, description="Payer's TIN (11-1111111)")
    recipient_tin: Optional[str] = Field(None, description="Recipient's TIN (111-11-1111)")
    payer_name: Optional[str] = Field(None, description="Payer's name")
    total_ordinary_dividends: Optional[float] = Field(None, description="Box 1a: Total ordinary dividends")
    qualified_dividends: Optional[float] = Field(None, description="Box 1b: Qualified dividends")
    total_capital_gain_distr: Optional[float] = Field(None, description="Box 2a: Total capital gain distribution")
    federal_income_tax_withheld: Optional[float] = Field(None, description="Box 4: Federal income tax withheld")

class Form5498SAFields(BaseModel):
    year: Optional[str] = Field(None, description="Tax Year")
    trustee_tin: Optional[str] = Field(None, description="Trustee’s or Issuer’s TIN (11-1111111)")
    participant_tin: Optional[str] = Field(None, description="Participant’s TIN (111-11-1111)")
    trustee_name: Optional[str] = Field(None, description="Trustee’s or Issuer’s name")
    hsa_contributions: Optional[float] = Field(None, description="Box 1: HSA contributions made in 2022")
    hsa_msa_rollover: Optional[float] = Field(None, description="Box 2: HSA or Archer MSA rollover contributions")

class BrokerageStatementFields(BaseModel):
    payer_name: Optional[str] = Field(None, description="Broker/Payer Name")
    payer_address: Optional[str] = Field(None, description="Broker/Payer Address")
    taxpayer_name: Optional[str] = Field(None, description="Taxpayer Name")
    taxpayer_address: Optional[str] = Field(None, description="Taxpayer Address")
    account_number: Optional[str] = Field(None, description="Account Number")
    summary_dividend_income: Optional[float] = Field(None, description="Total Dividends Summary")
    summary_interest_income: Optional[float] = Field(None, description="Total Interest Summary")
    summary_capital_gains: Optional[float] = Field(None, description="Total Capital Gains Summary")
