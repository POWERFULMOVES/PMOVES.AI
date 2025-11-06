const { expect } = require("chai");
const { ethers } = require("hardhat");
const { deployCoreFixture, loadFixture, time } = require("./fixtures");

const BASE = 10n ** 18n;
const LOCK_BONUS = 5n * 10n ** 17n;

function sqrtBigInt(value) {
  if (value < 0n) throw new Error("negative");
  if (value < 2n) return value;
  let x0 = value / 2n;
  let x1 = (x0 + value / x0) / 2n;
  while (x1 < x0) {
    x0 = x1;
    x1 = (x0 + value / x0) / 2n;
  }
  return x0;
}

describe("GroVault & CoopGovernor", function () {
  it("computes voting power with lock multiplier", async function () {
    const { alice, vault, groToken } = await loadFixture(deployCoreFixture);
    // Tier 1 scenario from the projections assumes a $5,000 long-term stake.
    const lockAmount = ethers.parseEther("5000");
    await groToken.connect(alice).approve(await vault.getAddress(), lockAmount);
    await vault.connect(alice).createLock(lockAmount, 4);

    const onChain = await vault.votingPower(alice.address);
    const sqrtAmount = sqrtBigInt(lockAmount);
    const multiplier = BASE + LOCK_BONUS * 3n; // 4 year lock = (1 + 0.5*(4-1))
    const expected = (sqrtAmount * multiplier) / BASE;
    expect(onChain).to.equal(expected);
  });

  it("enforces quadratic vote costs and executes proposals", async function () {
    const { alice, bob, vault, groToken, governor, votingPeriod } = await loadFixture(deployCoreFixture);

    // Alice mirrors the $5,000 cooperative lead allocation (4 year commitment).
    const aliceAmount = ethers.parseEther("5000");
    await groToken.connect(alice).approve(await vault.getAddress(), aliceAmount);
    await vault.connect(alice).createLock(aliceAmount, 4);

    // Bob represents the $3,000 community tier participant with a 2 year horizon.
    const bobAmount = ethers.parseEther("3000");
    await groToken.connect(bob).approve(await vault.getAddress(), bobAmount);
    await vault.connect(bob).createLock(bobAmount, 2);

    await governor.connect(alice).createProposal("Fund regenerative farm pilot");
    const proposalId = await governor.proposalCount();

    await expect(governor.connect(alice).castVote(proposalId, 0, true)).to.be.revertedWith("votes zero");

    await governor.connect(alice).castVote(proposalId, 90, true);
    const bobPower = await vault.votingPower(bob.address);
    const tooManyVotes = sqrtBigInt(bobPower) + 1n;
    await expect(governor.connect(bob).castVote(proposalId, tooManyVotes, true)).to.be.revertedWith("insufficient power");
    await governor.connect(bob).castVote(proposalId, 40, true);

    const tally = await governor.tallies(proposalId);
    expect(tally.forVotes).to.equal(130n);
    expect(tally.againstVotes).to.equal(0n);

    const bobSpent = await governor.spentVotingPower(proposalId, bob.address);
    expect(bobSpent).to.equal(40n * 40n);

    await expect(governor.execute(proposalId)).to.be.revertedWith("voting ongoing");
    await time.increase(Number(votingPeriod) + 1);
    await expect(governor.execute(proposalId))
      .to.emit(governor, "ProposalExecuted")
      .withArgs(proposalId, 130n, 0n);
  });
});
